"""Post-conditions, run against the OUTPUT databases (ID_STRATEGY section 6).

These are not unit tests: they run at the end of every real migration, on the
files just written, and a failure aborts the run. Two of them are load-bearing:

* **`id_registry[key] == MAX(id) + 1` for all 11 keys.** The strongest single
  check in the project: it catches under-seeding (a future `INSERT OR REPLACE`
  silently clobbering a migrated row), over-seeding (harmless, but it means a
  bug), and a missing key (silently reset to 1 by `ensure_keys()`).
* **every logged result row has its genesis op, and vice versa.** A result row
  without its op resolves to `None` on the user's first edit and is tombstoned;
  an op without its row is a phantom entity. Both directions are checked per
  entity kind, by recomputing `entity_key` from the row that was written.
"""

from __future__ import annotations

import json
import sqlite3

from .genesis import GENESIS_COMMIT_ID, LOGGED_ENTITIES, OP_CREATE, encode_key
from .ids import ID_REGISTRY_KEYS, REGISTRY_TABLES


class PostConditionError(AssertionError):
    pass


class PostConditions:
    def __init__(self, project_path, data_path, media_path):
        self.paths = {"project": project_path, "data": data_path,
                      "media": media_path}
        self.checks = []
        self.failures = []

    def _ok(self, name, detail=""):
        self.checks.append((name, True, detail))

    def _fail(self, name, detail):
        self.checks.append((name, False, detail))
        self.failures.append("%s: %s" % (name, detail))

    def run(self):
        conns = {k: sqlite3.connect("file:%s?mode=ro" % v, uri=True)
                 for k, v in self.paths.items()}
        try:
            self.check_registry(conns)
            self.check_genesis(conns["data"])
            self.check_sequence(conns["data"])
            self.check_properties(conns["data"])
            self.check_references(conns)
        finally:
            for conn in conns.values():
                conn.close()
        return self.failures

    def assert_ok(self):
        self.run()
        if self.failures:
            raise PostConditionError(
                "%d post-condition(s) failed after writing the project:\n  - %s"
                % (len(self.failures), "\n  - ".join(self.failures)))
        return self.checks

    # -- id_registry ---------------------------------------------------
    def check_registry(self, conns):
        rows = conns["project"].execute(
            "SELECT key, value FROM id_registry").fetchall()
        got = dict(rows)
        if set(got) != set(ID_REGISTRY_KEYS):
            self._fail("id_registry keys",
                       "expected exactly the 11 IdRegistry fields, got %s"
                       % sorted(got))
            return
        self._ok("id_registry keys", "all 11 present, none extra")
        for key in ID_REGISTRY_KEYS:
            raw = got[key]
            if raw is None:
                self._fail("id_registry[%s]" % key,
                           "NULL -- allocate() would raise TypeError")
                continue
            value = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
            if not isinstance(value, int) or isinstance(value, bool):
                self._fail("id_registry[%s]" % key,
                           "not a JSON integer: %r" % (raw,))
                continue
            db, table = REGISTRY_TABLES[key]
            row = conns[db].execute("SELECT MAX(id) FROM %s" % table).fetchone()
            expected = 1 if row[0] is None else row[0] + 1
            if value != expected:
                self._fail("id_registry[%s]" % key,
                           "is %d, expected MAX(%s.id)+1 = %d"
                           % (value, table, expected))
            elif value < 1:
                self._fail("id_registry[%s]" % key, "is %d, must be >= 1" % value)
            else:
                self._ok("id_registry[%s]" % key, "= %d" % value)

    # -- the genesis journal -------------------------------------------
    def check_genesis(self, data):
        n = data.execute("SELECT COUNT(*) FROM commits").fetchone()[0]
        if n:
            self._fail("commits empty",
                       "%d row(s): genesis is virtual, commit 0 must not exist" % n)
        else:
            self._ok("commits empty", "genesis is virtual")

        bad_op = data.execute(
            "SELECT COUNT(*) FROM entity_log WHERE op != ? OR commit_id != ?",
            (OP_CREATE, GENESIS_COMMIT_ID)).fetchone()[0]
        if bad_op:
            self._fail("entity_log ops", "%d row(s) are not (commit_id=0, op=1)" % bad_op)
        else:
            self._ok("entity_log ops", "all genesis OP_CREATE")

        total_rows = total_ops = 0
        for kind, meta in LOGGED_ENTITIES.items():
            logged = {k: c for k, c in data.execute(
                "SELECT entity_key, changes FROM entity_log "
                "WHERE entity_type = ? AND commit_id = ?",
                (kind, GENESIS_COMMIT_ID)).fetchall()}
            rows = data.execute(
                "SELECT %s, commit_id, operation, sequence FROM %s"
                % (", ".join(meta.pk_fields), meta.table)).fetchall()
            total_rows += len(rows)
            total_ops += len(logged)
            missing = wrong_stamp = bad_changes = 0
            seen = set()
            for row in rows:
                pk = row[:len(meta.pk_fields)]
                commit_id, operation, sequence = row[len(meta.pk_fields):]
                key = encode_key(pk)
                seen.add(key)
                if key not in logged:
                    missing += 1
                elif meta.presence_only and logged[key] is not None:
                    bad_changes += 1
                elif not meta.presence_only and logged[key] is None:
                    bad_changes += 1
                if (commit_id, operation, sequence) != (GENESIS_COMMIT_ID, OP_CREATE, 1):
                    wrong_stamp += 1
            orphan_ops = len(set(logged) - seen)
            name = "genesis pairing [%s]" % kind
            if missing:
                self._fail(name, "%d result row(s) with NO genesis op -- they "
                                 "would be tombstoned on first edit" % missing)
            elif orphan_ops:
                self._fail(name, "%d genesis op(s) with no result row" % orphan_ops)
            elif wrong_stamp:
                self._fail(name, "%d result row(s) not stamped "
                                 "(commit_id=0, operation=1, sequence=1)" % wrong_stamp)
            elif bad_changes:
                self._fail(name, "%d op(s) with the wrong changes shape "
                                 "(presence_only entities must have NULL)" % bad_changes)
            else:
                self._ok(name, "%d row(s) paired" % len(rows))
        if total_rows != total_ops:
            self._fail("genesis totals",
                       "%d logged rows vs %d genesis ops" % (total_rows, total_ops))
        else:
            self._ok("genesis totals", "%d logged rows == %d genesis ops"
                     % (total_rows, total_ops))

    def check_sequence(self, data):
        row = data.execute("SELECT id FROM sequence").fetchall()
        if len(row) != 1:
            self._fail("sequence seed row",
                       "%d row(s); an empty table makes the writer return 1 "
                       "forever and delta sync never advances" % len(row))
            return
        watermark = row[0][0]
        tables = ["file_sources", "folders", "files", "instances", "entity_log"]
        tables += [m.table for m in LOGGED_ENTITIES.values()]
        worst = 0
        for table in tables:
            got = data.execute("SELECT MAX(sequence) FROM %s" % table).fetchone()[0]
            worst = max(worst, got or 0)
        if watermark < worst:
            self._fail("sequence watermark",
                       "sequence.id = %s < max row sequence %s" % (watermark, worst))
        else:
            self._ok("sequence watermark", "sequence.id = %s >= %s" % (watermark, worst))

    def check_properties(self, data):
        low = data.execute(
            "SELECT COUNT(*) FROM properties WHERE id < 1").fetchone()[0]
        if low:
            self._fail("property ids", "%d propert(ies) with id < 1" % low)
        else:
            self._ok("property ids", "all >= 1")
        n_sys = data.execute(
            "SELECT COUNT(*) FROM properties WHERE system_key IS NOT NULL").fetchone()[0]
        if n_sys != 9:
            self._fail("system properties", "expected 9, found %d" % n_sys)
            return
        max_user = data.execute(
            "SELECT MAX(id) FROM properties WHERE system_key IS NULL").fetchone()[0]
        min_sys = data.execute(
            "SELECT MIN(id) FROM properties WHERE system_key IS NOT NULL").fetchone()[0]
        if max_user is not None and max_user >= min_sys:
            self._fail("system properties",
                       "system ids start at %d but a legacy property has id %d "
                       "-- they must be allocated above every legacy id"
                       % (min_sys, max_user))
        else:
            self._ok("system properties",
                     "9 rows, ids %d..%d, above every legacy property"
                     % (min_sys, min_sys + 8))

    # -- the reference graph -------------------------------------------
    def check_references(self, conns):
        data, media = conns["data"], conns["media"]
        bad = data.execute(
            "SELECT COUNT(*) FROM instances WHERE file_id IS NOT id").fetchone()[0]
        if bad:
            self._fail("instances.file_id", "%d row(s) where file_id != id" % bad)
        else:
            self._ok("instances.file_id", "== instances.id everywhere")

        orphans = [
            ("folders.source_id", "SELECT COUNT(*) FROM folders f WHERE f.source_id "
             "NOT IN (SELECT id FROM file_sources)"),
            ("folders.parent", "SELECT COUNT(*) FROM folders f WHERE f.parent IS NOT NULL "
             "AND f.parent NOT IN (SELECT id FROM folders)"),
            ("files.folder_id", "SELECT COUNT(*) FROM files WHERE folder_id "
             "NOT IN (SELECT id FROM folders)"),
            ("instances.file_id", "SELECT COUNT(*) FROM instances WHERE file_id "
             "NOT IN (SELECT id FROM files)"),
            ("properties.property_group_id", "SELECT COUNT(*) FROM properties "
             "WHERE property_group_id IS NOT NULL AND property_group_id NOT IN "
             "(SELECT id FROM property_groups)"),
            ("tags.list_id", "SELECT COUNT(*) FROM tags WHERE list_id NOT IN "
             "(SELECT id FROM properties)"),
            ("instance_values.property_id", "SELECT COUNT(*) FROM instance_values "
             "WHERE property_id NOT IN (SELECT id FROM properties)"),
            ("instance_values.instance_id", "SELECT COUNT(*) FROM instance_values "
             "WHERE instance_id NOT IN (SELECT id FROM instances)"),
            ("sha1_values.property_id", "SELECT COUNT(*) FROM sha1_values "
             "WHERE property_id NOT IN (SELECT id FROM properties)"),
            ("sha1_values.sha1", "SELECT COUNT(*) FROM sha1_values WHERE sha1 "
             "NOT IN (SELECT sha1 FROM instances)"),
            ("instance_tag_values.tag_id", "SELECT COUNT(*) FROM instance_tag_values "
             "WHERE tag_id NOT IN (SELECT id FROM tags)"),
            ("instance_tag_values.instance_id", "SELECT COUNT(*) FROM instance_tag_values "
             "WHERE instance_id NOT IN (SELECT id FROM instances)"),
            ("sha1_tag_values.tag_id", "SELECT COUNT(*) FROM sha1_tag_values "
             "WHERE tag_id NOT IN (SELECT id FROM tags)"),
            ("sha1_tag_values.sha1", "SELECT COUNT(*) FROM sha1_tag_values WHERE sha1 "
             "NOT IN (SELECT sha1 FROM instances)"),
        ]
        before = len(self.failures)
        for name, sql in orphans:
            n = data.execute(sql).fetchone()[0]
            if n:
                self._fail("orphans in %s" % name, "%d row(s)" % n)
        if len(self.failures) == before:
            self._ok("reference graph",
                     "no orphans across the %d implicit refs" % len(orphans))

        # tags.parents is a JSON int list of tag ids in the same list
        tag_lists = {tid: lid for tid, lid in
                     data.execute("SELECT id, list_id FROM tags")}
        bad_parents = 0
        for tid, parents in data.execute("SELECT id, parents FROM tags"):
            for pid in json.loads(parents or "[]"):
                if pid not in tag_lists or tag_lists[pid] != tag_lists[tid]:
                    bad_parents += 1
        if bad_parents:
            self._fail("tags.parents", "%d dangling or cross-list parent(s)" % bad_parents)
        else:
            self._ok("tags.parents", "every parent exists and shares the list")

        # maps.data embeds instance ids and is copied verbatim -- the whole
        # preserve-ids policy exists for this row
        known = {r[0] for r in data.execute("SELECT id FROM instances")}
        missing = 0
        for (blob,) in media.execute("SELECT data FROM maps"):
            if not blob:
                continue
            values = json.loads(blob)
            missing += sum(1 for v in values[::3]
                           if isinstance(v, int) and v not in known)
        if missing:
            self._fail("maps.data", "%d embedded instance id(s) do not exist" % missing)
        else:
            self._ok("maps.data", "every embedded instance id exists")

        for table, ref in (("images", "image_types"), ("vectors", "vector_types")):
            n = media.execute("SELECT COUNT(*) FROM %s WHERE type_id NOT IN "
                              "(SELECT id FROM %s)" % (table, ref)).fetchone()[0]
            if n:
                self._fail("%s.type_id" % table, "%d orphan row(s)" % n)
        self._ok("media type ids", "images/vectors reference a declared type")
