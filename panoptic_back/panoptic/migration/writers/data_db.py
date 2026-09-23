"""data.db -- the journal plus every entity the collection is made of.

Three classes of table, three different writes (MAPPING section 2):

* **structural** (`file_sources`, `folders`, `files`, `instances`) -- columns and
  `sequence` only. No `commit_id`, no `operation`, and they must never appear in
  `entity_log`.
* **logged** (the other eight) -- every row goes through `Genesis.emit`, which
  writes the result row and its genesis op together. See `genesis.py`.
* **neither** -- `tag_lists`, which nothing in the target ever inserts into and
  which CLAUDE.md's signed-off decision says to leave empty
  (`property.tag_list_id = property.id` is the convention everything joins on).

`commits` is left empty: genesis is virtual, so the first real post-migration
commit gets id 1 from `COALESCE(MAX(id),0)+1`.
"""

from __future__ import annotations

from ..schema import create_db
from .genesis import SEQUENCE, Genesis
from .ids import SystemPropertyPlan

#: the one synthesised `file_sources` row every folder points at. `dtype='local'`
#: is load-bearing: `ensure_local_file_source()` looks the row up by it and will
#: not create a second one, and `resolve_image_ref` branches on it.
LOCAL_SOURCE_ID = 1

#: PIL writes `img.format.lower()`, which is `jpeg`; leaving legacy `jpg` would
#: make the `format` system property disagree with post-migration imports.
FORMAT_ALIASES = {"jpg": "jpeg", "jpe": "jpeg", "tif": "tiff"}


def normalise_format(extension):
    if not extension:
        return None
    ext = str(extension).lower().lstrip(".")
    return FORMAT_ALIASES.get(ext, ext)


class DataDbWriter:
    def __init__(self, path, ir, report=None):
        self.path = path
        self.ir = ir
        self.report = report
        self.conn = None
        self.system = SystemPropertyPlan(ir.max_ids()["properties"])
        self.stats = {}
        self.skipped = {}

    # -- plumbing ------------------------------------------------------
    def _skip(self, reason, n=1):
        self.skipped[reason] = self.skipped.get(reason, 0) + n

    def write(self):
        self.conn = create_db(self.path, "data")
        try:
            g = Genesis(self.conn)
            self.write_structural()
            self.write_properties(g)
            self.write_property_groups(g)
            self.write_tags(g)
            self.write_values(g)
            self.write_tag_values(g)
            self.conn.commit()
            self.stats["entity_log"] = sum(g.counts.values())
            self.stats["logged"] = dict(g.counts)
            if g.duplicates:
                for kind, n in g.duplicates.items():
                    self._skip("duplicate %s primary key" % kind, n)
        finally:
            self.conn.close()
            self.conn = None
        return self.stats

    # -- structural ----------------------------------------------------
    def write_structural(self):
        c = self.conn
        c.execute("INSERT INTO file_sources "
                  "(id, dtype, name, root_url, metadata, sync_status, sequence) "
                  "VALUES (?,?,?,?,?,?,?)",
                  (LOCAL_SOURCE_ID, "local", "local_filesystem", None, None,
                   None, SEQUENCE))
        self.stats["file_sources"] = 1

        folder_ids = set()
        for f in self.ir.folders:
            c.execute("INSERT INTO folders (id, source_id, path, name, parent, "
                      "sequence) VALUES (?,?,?,?,?,?)",
                      (f.id, LOCAL_SOURCE_ID, f.path, f.name, f.parent, SEQUENCE))
            folder_ids.add(f.id)
        self.stats["folders"] = len(folder_ids)

        # a folder whose parent is gone would be invisible in the tree
        for f in self.ir.folders:
            if f.parent is not None and f.parent not in folder_ids:
                c.execute("UPDATE folders SET parent = NULL WHERE id = ?", (f.id,))
                self._skip("folder parent dangling (re-rooted)")

        files = instances = 0
        for inst in self.ir.instances:
            if inst.folder_id not in folder_ids:
                self._skip("instance with unknown folder_id")
                continue
            c.execute("INSERT INTO files (id, name, folder_id, sha1, width, "
                      "height, format, created_at, sequence) "
                      "VALUES (?,?,?,?,?,?,?,?,?)",
                      (inst.id, inst.name, inst.folder_id, inst.sha1, inst.width,
                       inst.height, normalise_format(inst.extension),
                       inst.created_at, SEQUENCE))
            # file_id == instance id: the two id spaces are independent in the
            # target, and reusing the legacy id keeps `maps.data` and every
            # instance-keyed value a straight copy (ID_STRATEGY section 2.3).
            c.execute("INSERT INTO instances (id, file_id, sha1, sequence) "
                      "VALUES (?,?,?,?)",
                      (inst.id, inst.id, inst.sha1, SEQUENCE))
            files += 1
            instances += 1
        self.stats["files"] = files
        self.stats["instances"] = instances
        self.instance_ids = {i.id for i in self.ir.instances}
        self.sha1s = {i.sha1 for i in self.ir.instances}

    # -- logged --------------------------------------------------------
    def write_properties(self, g):
        group_ids = {pg.id for pg in self.ir.property_groups}
        n = 0
        for p in self.ir.properties:
            if p.id < 1:
                self._skip("property with a non-positive id")
                continue
            group = p.property_group_id if p.property_group_id in group_ids else None
            if p.property_group_id is not None and group is None:
                # v5/v6 store an unresolved importer placeholder here (a
                # negative counter id, e.g. -101, that was never rewritten on
                # insert). Nothing in the target resolves a negative id, and
                # guessing which group was meant would invent data: drop the
                # reference, keep the property, report it (ID_STRATEGY 4.3).
                self._skip("property.property_group_id %s (reference dropped, "
                           "the property itself is kept)"
                           % ("is an unresolved importer placeholder"
                              if p.property_group_id < 0
                              else "names no property group"))
            row = {"id": p.id, "dtype": p.dtype, "mode": p.mode, "name": p.name,
                   "access": "write",            # legacy has no read-only flag (L2)
                   "tag_list_id": p.id,          # signed off: list id == property id
                   "system_key": None,
                   "property_group_id": group}
            n += g.emit("property", row)
        self.property_index = {p.id: p for p in self.ir.properties}

        for prop_id, sp in self.system.rows():
            g.emit("property", {"id": prop_id, "dtype": sp.dtype, "mode": sp.mode,
                                "name": sp.key, "access": "read",
                                "tag_list_id": None, "system_key": sp.key,
                                "property_group_id": None})
        self.stats["properties"] = n
        self.stats["system_properties"] = len(self.system.ids)

    def write_property_groups(self, g):
        n = 0
        for pg in self.ir.property_groups:
            n += g.emit("group", {"id": pg.id, "name": pg.name})
        self.stats["property_groups"] = n

    def write_tags(self, g):
        known = {t.id: t for t in self.ir.tags}
        n = 0
        for t in self.ir.tags:
            # a dangling or cross-list parent makes the tag unreachable in the
            # UI tree, so it is dropped rather than written
            parents = []
            for pid in t.parents:
                parent = known.get(pid)
                if parent is None or parent.property_id != t.property_id:
                    self._skip("tag parent dangling or cross-list")
                    continue
                parents.append(pid)
            row = {"id": t.id, "list_id": t.property_id,
                   "parents": _json_list(parents), "value": t.value,
                   "color": t.color}
            n += g.emit("tag", row,
                        changes_values={"list_id": t.property_id,
                                        "value": t.value, "color": t.color},
                        sets={"parents": parents})
        self.stats["tags"] = n

    def write_values(self, g):
        props = self.property_index
        counts = {"instance_value": 0, "sha1_value": 0}
        for kind, rows, key_field, key_ok in (
                ("instance_value", self.ir.instance_values, "instance_id",
                 lambda k: k in self.instance_ids),
                ("sha1_value", self.ir.sha1_values, "sha1",
                 lambda k: k in self.sha1s)):
            for v in rows:
                prop = props.get(v.property_id)
                if prop is None:
                    self._skip("value for an unknown property")
                    continue
                if prop.is_tag:
                    # would insert cleanly, pass a row count and never be read
                    self._skip("tag-dtype value in a generic value table")
                    continue
                if not key_ok(v.key):
                    self._skip("value for an unknown %s" % key_field)
                    continue
                if v.raw is None:
                    self._skip("value row with a NULL payload")
                    continue
                row = {"property_id": v.property_id, key_field: v.key,
                       "value": v.raw}
                # the column takes the legacy JSON *text*; the snapshot needs
                # the decoded object (MAPPING 6.3)
                if g.emit(kind, row, changes_values={"value": v.value}):
                    counts[kind] += 1
        self.stats["instance_values"] = counts["instance_value"]
        self.stats["sha1_values"] = counts["sha1_value"]
        self.stats["file_values"] = 0     # no legacy mode maps to file_values

    def write_tag_values(self, g):
        props = self.property_index
        tags = {t.id: t for t in self.ir.tags}
        counts = {"instance_tag_value": 0, "sha1_tag_value": 0}
        for kind, rows, key_field, key_ok in (
                ("instance_tag_value", self.ir.instance_tag_values, "instance_id",
                 lambda k: k in self.instance_ids),
                ("sha1_tag_value", self.ir.sha1_tag_values, "sha1",
                 lambda k: k in self.sha1s)):
            for key, property_id, tag_id in rows:
                prop = props.get(property_id)
                tag = tags.get(tag_id)
                if prop is None:
                    self._skip("tag assignment for an unknown property")
                    continue
                if tag is None:
                    self._skip("tag assignment for an unknown tag")
                    continue
                if tag.property_id != property_id:
                    self._skip("tag assignment crossing properties")
                    continue
                if not key_ok(key):
                    self._skip("tag assignment for an unknown %s" % key_field)
                    continue
                row = {key_field: key, "property_id": property_id,
                       "tag_id": tag_id}
                if g.emit(kind, row):       # presence_only: changes is NULL
                    counts[kind] += 1
        self.stats["instance_tag_values"] = counts["instance_tag_value"]
        self.stats["sha1_tag_values"] = counts["sha1_tag_value"]


def _json_list(values):
    import json
    return json.dumps(list(values), separators=(",", ":"))


def write_data_db(path, ir, report=None):
    w = DataDbWriter(path, ir, report)
    stats = w.write()
    return w, stats
