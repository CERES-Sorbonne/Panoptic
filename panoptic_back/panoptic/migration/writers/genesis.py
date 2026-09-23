"""The genesis journal: the one code path that writes a logged entity.

Everything in `analysis/MAPPING.md` section 6 and `analysis/TARGET_NOTES.md`
section 4 lives here, in one place, for one reason:

    A result row written **without** its `entity_log` genesis op resolves from
    an empty op set to `None` on the user's first edit of that entity, and the
    row is then tombstoned. The data disappears silently, days after the
    migration ran. It is the single most dangerous failure mode in the project.

So no caller ever inserts into a logged table directly. They call
`Genesis.emit(kind, pk, columns, changes_fields)` and the pair -- result row and
`entity_log` op -- is written together or not at all.

Facts encoded here, each verified against the target:

* genesis is **virtual**: `commits` stays empty and every op carries
  `commit_id = 0`, which `DataWriter._enabled_ops` matches unconditionally;
* `OP_CREATE = 1`, `OP_UPDATE = 0` (not 2), `OP_DELETE = -1`;
* `entity_key = json.dumps(list(pk), separators=(',',':'))` in
  `LOGGED_ENTITY_META` **pk order**, which is not the table's column order for
  the junction tables;
* `changes` is the full base image for a create -- every non-`None` data field,
  set fields as an all-add delta -- and **NULL** for the two `presence_only`
  junction kinds;
* every migrated row and every op carries `sequence = 1`.
"""

from __future__ import annotations

import json

GENESIS_COMMIT_ID = 0
OP_UPDATE = 0
OP_CREATE = 1
OP_DELETE = -1
#: every migrated row carries the same delta-sync stamp (ID_STRATEGY 1.3)
SEQUENCE = 1


def encode_key(pk):
    """`resolver.encode_key`: a JSON *list*, compact separators, pk order."""
    return json.dumps(list(pk), separators=(",", ":"))


class LoggedEntity:
    """One row of the target's `LOGGED_ENTITY_META`, as the writer needs it."""

    def __init__(self, kind, table, columns, pk_fields, data_fields,
                 set_fields=(), presence_only=False):
        self.kind = kind
        self.table = table
        self.columns = columns          # result-table column order (no journal cols)
        self.pk_fields = pk_fields      # entity_key order -- NOT column order
        self.data_fields = data_fields
        self.set_fields = set_fields
        self.presence_only = presence_only


#: Mirrors `data/create.py::LOGGED_ENTITY_META` exactly. `entity_type` for
#: property groups is 'group', not 'property_group' -- an easy and silent error.
LOGGED_ENTITIES = {e.kind: e for e in (
    LoggedEntity(
        "property", "properties",
        ("id", "dtype", "mode", "name", "access", "tag_list_id", "system_key",
         "property_group_id"),
        ("id",),
        ("dtype", "mode", "name", "access", "tag_list_id", "system_key",
         "property_group_id")),
    LoggedEntity("group", "property_groups", ("id", "name"), ("id",), ("name",)),
    LoggedEntity("tag", "tags", ("id", "list_id", "parents", "value", "color"),
                 ("id",), ("list_id", "value", "color"), ("parents",)),
    LoggedEntity("instance_value", "instance_values",
                 ("property_id", "instance_id", "value"),
                 ("property_id", "instance_id"), ("value",)),
    LoggedEntity("sha1_value", "sha1_values",
                 ("property_id", "sha1", "value"),
                 ("property_id", "sha1"), ("value",)),
    LoggedEntity("file_value", "file_values",
                 ("property_id", "file_id", "value"),
                 ("property_id", "file_id"), ("value",)),
    LoggedEntity("instance_tag_value", "instance_tag_values",
                 ("instance_id", "property_id", "tag_id"),
                 ("instance_id", "property_id", "tag_id"), (), (), True),
    LoggedEntity("sha1_tag_value", "sha1_tag_values",
                 ("sha1", "property_id", "tag_id"),
                 ("sha1", "property_id", "tag_id"), (), (), True),
)}


class Genesis:
    """Writes logged result rows and their genesis ops, atomically, in pairs."""

    def __init__(self, conn):
        self.conn = conn
        self.counts = {}          # kind -> rows emitted
        self.duplicates = {}      # kind -> rows skipped as duplicate pks

    # -- the only entry point ------------------------------------------
    def emit(self, kind, row, changes_values=None, sets=None):
        """Write one logged entity.

        `row` maps result-table column -> value (journal columns excluded).
        `changes_values` is the *Python* (decoded) value of each data field for
        the `changes` snapshot; it defaults to `row`, which is right for every
        entity except the value tables, where the column holds the legacy JSON
        *text* and the snapshot needs the decoded object (MAPPING 6.3).
        `sets` maps each set field to its element list (tags.parents).
        """
        meta = LOGGED_ENTITIES[kind]
        pk = tuple(row[f] for f in meta.pk_fields)
        key = encode_key(pk)
        cols = list(meta.columns) + ["commit_id", "operation", "sequence"]
        values = [row.get(c) for c in meta.columns] + \
                 [GENESIS_COMMIT_ID, OP_CREATE, SEQUENCE]

        changes = None
        if not meta.presence_only:
            src = row if changes_values is None else changes_values
            snapshot = {}
            for field in meta.data_fields:
                val = src.get(field)
                if val is not None:            # None fields are omitted, not null
                    snapshot[field] = val
            for field in meta.set_fields:
                elements = (sets or {}).get(field) or []
                if elements:                   # omit the key entirely when empty
                    snapshot[field] = {"add": sorted(elements), "remove": []}
            changes = json.dumps(snapshot)

        cur = self.conn.execute(
            "INSERT OR IGNORE INTO %s (%s) VALUES (%s)"
            % (meta.table, ", ".join(cols), ", ".join("?" * len(cols))), values)
        if cur.rowcount == 0:
            # duplicate primary key in the legacy data: the row is already
            # there, and writing a second op for the same entity_key would be
            # a lie. Count it and move on.
            self.duplicates[kind] = self.duplicates.get(kind, 0) + 1
            return False
        self.conn.execute(
            "INSERT INTO entity_log "
            "(entity_type, entity_key, commit_id, op, changes, sequence) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (kind, key, GENESIS_COMMIT_ID, OP_CREATE, changes, SEQUENCE))
        self.counts[kind] = self.counts.get(kind, 0) + 1
        return True
