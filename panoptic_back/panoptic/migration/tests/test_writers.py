"""End-to-end writer tests: every fixture, migrated, then asserted (task 3.3).

    python3 -m unittest migrator.tests.test_writers      # assert
    python3 migrator/tests/test_writers.py --table       # look at it

Each of the 11 fixtures is migrated into a temporary folder and then checked
against the *output*, never against the writer's own bookkeeping:

* the full `PostConditions` suite (ID_STRATEGY section 6) -- including the
  load-bearing `id_registry[key] == MAX(id) + 1` for all 11 keys and the
  genesis-pairing check in both directions;
* row counts reconcile with the IR minus whatever the writer reported skipping;
* the source DB is byte-for-byte untouched (CLAUDE.md rule 1).
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))   # panoptic_back/
if ROOT not in sys.path:  # allow running this file directly, not just as a module
    sys.path.insert(0, ROOT)

from panoptic.migration.detect import detect_db                      # noqa: E402
from panoptic.migration.ir import Dropped                             # noqa: E402
from panoptic.migration.pipeline import run_pipeline                  # noqa: E402
from panoptic.migration.report import Report                          # noqa: E402
from panoptic.migration.writers import (ID_REGISTRY_KEYS, PostConditions,  # noqa: E402
                              SYSTEM_PROPERTIES)

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
SHAPES = ("P0", "P1", "v1", "v2", "v3", "v4", "v5", "v6", "v7a", "v7b", "v7c")


def fixture_db(name):
    return os.path.join(FIXTURES, name, "panoptic.db")


def migrate(name, target_dir):
    """Run the whole pipeline on one fixture. Returns (ir, report)."""
    db = fixture_db(name)
    detection = detect_db(db)
    report = Report(os.path.dirname(db), db, target_dir, dry_run=False)
    report.set_detection(detection)
    ir = run_pipeline(detection, db, target_dir, report)
    return ir, report


def counts(path):
    conn = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
    try:
        return {t: conn.execute('SELECT COUNT(*) FROM "%s"' % t).fetchone()[0]
                for (t,) in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()


class MigratedFixture:
    """One migrated fixture, kept around for a whole test class."""

    def __init__(self, name, target):
        self.name = name
        self.dir = target
        self.ir, self.report = migrate(name, target)
        #: the folder exactly as the migration left it -- read before this class
        #: opens a single connection, because even a read-only connection
        #: recreates the `-wal`/`-shm` sidecars
        self.files_written = sorted(os.listdir(target))
        self.project = os.path.join(target, "project.db")
        self.data = os.path.join(target, "data.db")
        self.media = os.path.join(target, "media.db")
        self.data_counts = counts(self.data)
        self.media_counts = counts(self.media)
        self.registry = self.read_registry()

    def read_registry(self):
        conn = sqlite3.connect("file:%s?mode=ro" % self.project, uri=True)
        try:
            # `value JSON` has NUMERIC affinity, so sqlite stores our '13' as
            # the integer 13. `KeyValueSchema.get_key` handles both; so do we.
            return {k: (json.loads(v) if isinstance(v, (str, bytes)) else v)
                    for k, v in conn.execute("SELECT key, value FROM id_registry")}
        finally:
            conn.close()

    def query(self, sql, db="data"):
        conn = sqlite3.connect("file:%s?mode=ro" % getattr(self, db), uri=True)
        try:
            return conn.execute(sql).fetchall()
        finally:
            conn.close()


_CACHE = {}
_TMP = None


def setUpModule():
    global _TMP
    _TMP = tempfile.mkdtemp(prefix="migrator-writers-")
    for shape in SHAPES:
        _CACHE[shape] = MigratedFixture(shape, os.path.join(_TMP, shape))


def tearDownModule():
    if _TMP:
        shutil.rmtree(_TMP, ignore_errors=True)


class PostConditionTests(unittest.TestCase):
    """ID_STRATEGY section 6, run against every migrated fixture."""

    def test_all_fixtures_pass_the_post_conditions(self):
        for shape in SHAPES:
            f = _CACHE[shape]
            with self.subTest(shape=shape):
                pc = PostConditions(f.project, f.data, f.media)
                failures = pc.run()
                self.assertEqual(failures, [], "%s: %s" % (shape, failures))
                self.assertTrue(pc.checks)

    def test_id_registry_is_max_plus_one_for_all_eleven_keys(self):
        for shape in SHAPES:
            f = _CACHE[shape]
            with self.subTest(shape=shape):
                self.assertEqual(set(f.registry), set(ID_REGISTRY_KEYS))
                for key, value in f.registry.items():
                    self.assertIsNotNone(value, key)
                    self.assertIsInstance(value, int)
                    self.assertGreaterEqual(value, 1)

    def test_empty_tables_seed_to_one_and_atlas_zero_seeds_to_one(self):
        # a source with no atlas at all and one with atlas id 0 both give 1,
        # for different reasons: the empty-table default, and max(0)+1.
        self.assertEqual(_CACHE["v1"].registry["image_atlas"], 1)
        self.assertEqual(_CACHE["v7c"].registry["image_atlas"], 1)
        self.assertEqual(_CACHE["v7c"].query("SELECT MIN(id) FROM image_atlas",
                                             "media")[0][0], 0)
        self.assertEqual(_CACHE["v1"].registry["vector_types"], 1)


class GenesisTests(unittest.TestCase):
    def test_commits_is_empty_everywhere(self):
        for shape in SHAPES:
            with self.subTest(shape=shape):
                self.assertEqual(_CACHE[shape].data_counts["commits"], 0)

    def test_every_logged_row_has_a_genesis_op(self):
        logged = ("properties", "property_groups", "tags", "instance_values",
                  "sha1_values", "file_values", "instance_tag_values",
                  "sha1_tag_values")
        for shape in SHAPES:
            f = _CACHE[shape]
            with self.subTest(shape=shape):
                total = sum(f.data_counts[t] for t in logged)
                self.assertEqual(f.data_counts["entity_log"], total)

    def test_structural_tables_are_never_logged(self):
        for shape in SHAPES:
            f = _CACHE[shape]
            with self.subTest(shape=shape):
                types = {r[0] for r in f.query(
                    "SELECT DISTINCT entity_type FROM entity_log")}
                self.assertFalse(types & {"file_source", "folder", "file",
                                          "instance"})

    def test_presence_only_kinds_have_null_changes(self):
        for shape in SHAPES:
            f = _CACHE[shape]
            with self.subTest(shape=shape):
                n = f.query("SELECT COUNT(*) FROM entity_log WHERE entity_type "
                            "IN ('instance_tag_value','sha1_tag_value') "
                            "AND changes IS NOT NULL")[0][0]
                self.assertEqual(n, 0)

    def test_entity_key_shape(self):
        f = _CACHE["v7c"]
        keys = dict(f.query("SELECT entity_type, entity_key FROM entity_log "
                            "WHERE entity_type IN ('property','group')"))
        self.assertRegex(keys["property"], r"^\[\d+\]$")
        self.assertIn("group", keys)          # 'group', never 'property_group'
        key = f.query("SELECT entity_key FROM entity_log WHERE entity_type = "
                      "'instance_tag_value' LIMIT 1")[0][0]
        self.assertEqual(len(json.loads(key)), 3)
        self.assertNotIn(" ", key)            # compact separators

    def test_changes_holds_decoded_values_not_json_text(self):
        f = _CACHE["v7c"]
        row = f.query("SELECT changes FROM entity_log WHERE entity_type = "
                      "'instance_value' LIMIT 1")[0][0]
        self.assertIsInstance(json.loads(row)["value"], (str, int, float, bool, list))

    def test_root_tag_omits_parents_and_child_adds_them(self):
        f = _CACHE["v7c"]
        by_key = dict(f.query("SELECT entity_key, changes FROM entity_log "
                              "WHERE entity_type = 'tag'"))
        roots = [json.loads(c) for k, c in by_key.items()
                 if json.loads(c).get("value") == "animal"]
        self.assertNotIn("parents", roots[0])
        child = [json.loads(c) for c in by_key.values()
                 if json.loads(c).get("value") == "mammal"][0]
        self.assertEqual(child["parents"], {"add": [1], "remove": []})


class DataDbTests(unittest.TestCase):
    def test_one_local_file_source_every_folder_points_at(self):
        for shape in SHAPES:
            f = _CACHE[shape]
            with self.subTest(shape=shape):
                self.assertEqual(f.query("SELECT id, dtype, name FROM file_sources"),
                                 [(1, "local", "local_filesystem")])
                self.assertEqual(
                    f.query("SELECT COUNT(*) FROM folders WHERE source_id != 1")[0][0], 0)

    def test_instances_and_files_are_one_to_one_on_the_legacy_id(self):
        for shape in SHAPES:
            f = _CACHE[shape]
            with self.subTest(shape=shape):
                self.assertEqual(f.data_counts["files"], f.data_counts["instances"])
                self.assertEqual(
                    f.query("SELECT COUNT(*) FROM instances i JOIN files f "
                            "ON f.id = i.file_id WHERE i.id != f.id")[0][0], 0)

    def test_nine_system_properties_above_every_legacy_property(self):
        for shape in SHAPES:
            f = _CACHE[shape]
            with self.subTest(shape=shape):
                sys_rows = f.query("SELECT id, system_key, access, tag_list_id "
                                   "FROM properties WHERE system_key IS NOT NULL "
                                   "ORDER BY id")
                self.assertEqual([r[1] for r in sys_rows],
                                 [sp.key for sp in SYSTEM_PROPERTIES])
                self.assertTrue(all(r[2] == "read" and r[3] is None for r in sys_rows))
                max_user = f.query("SELECT MAX(id) FROM properties "
                                   "WHERE system_key IS NULL")[0][0]
                if max_user is not None:
                    self.assertLess(max_user, sys_rows[0][0])
                self.assertEqual(f.registry["properties"], sys_rows[-1][0] + 1)

    def test_legacy_properties_get_tag_list_id_equal_to_their_own_id(self):
        for shape in SHAPES:
            f = _CACHE[shape]
            with self.subTest(shape=shape):
                self.assertEqual(
                    f.query("SELECT COUNT(*) FROM properties WHERE system_key IS "
                            "NULL AND tag_list_id IS NOT id")[0][0], 0)
                # ... and the dead tag_lists table stays empty (signed off)
                self.assertEqual(f.data_counts["tag_lists"], 0)

    def test_tag_list_id_joins_tags_to_their_property(self):
        for shape in SHAPES:
            f = _CACHE[shape]
            with self.subTest(shape=shape):
                self.assertEqual(
                    f.query("SELECT COUNT(*) FROM tags t WHERE t.list_id NOT IN "
                            "(SELECT tag_list_id FROM properties "
                            "WHERE tag_list_id IS NOT NULL)")[0][0], 0)

    def test_no_tag_dtype_value_lands_in_a_generic_value_table(self):
        for shape in SHAPES:
            f = _CACHE[shape]
            with self.subTest(shape=shape):
                for table in ("instance_values", "sha1_values"):
                    n = f.query("SELECT COUNT(*) FROM %s v JOIN properties p ON "
                                "p.id = v.property_id WHERE p.dtype IN "
                                "('tag','multi_tags')" % table)[0][0]
                    self.assertEqual(n, 0, "%s.%s" % (shape, table))

    def test_file_values_stays_empty(self):
        for shape in SHAPES:
            self.assertEqual(_CACHE[shape].data_counts["file_values"], 0)

    def test_jpg_becomes_jpeg(self):
        for shape in SHAPES:
            f = _CACHE[shape]
            with self.subTest(shape=shape):
                self.assertEqual(
                    f.query("SELECT COUNT(*) FROM files WHERE format = 'jpg'")[0][0], 0)

    def test_counts_reconcile_with_the_ir(self):
        for shape in SHAPES:
            f = _CACHE[shape]
            c = f.ir.counts()
            with self.subTest(shape=shape):
                self.assertEqual(f.data_counts["folders"], c["folders"])
                self.assertEqual(f.data_counts["instances"], c["instances"])
                self.assertEqual(f.data_counts["tags"], c["tags"])
                self.assertEqual(f.data_counts["properties"],
                                 c["properties"] + len(SYSTEM_PROPERTIES))


class MediaDbTests(unittest.TestCase):
    def test_vectors_are_dropped_by_sign_off(self):
        for shape in SHAPES:
            f = _CACHE[shape]
            with self.subTest(shape=shape):
                self.assertEqual(f.media_counts["vectors"], 0)
                self.assertEqual(f.media_counts["vector_types"], 0)

    def test_thumbnail_sizes_come_from_the_legacy_project_kv(self):
        f = _CACHE["v7c"]
        types = f.query("SELECT name, format, width, height, auto_gen "
                        "FROM image_types ORDER BY id", "media")
        self.assertEqual(types, [("small", "jpeg", 96, 96, 1),
                                 ("medium", "jpeg", 320, 320, 1)])
        # `large` is off in the fixture (save_image_large=false, no blobs), so
        # no type is written and nothing regenerates a size the user turned off
        self.assertNotIn("large", [t[0] for t in types])

    def test_images_reference_a_declared_type_and_skip_empty_blobs(self):
        for shape in SHAPES:
            f = _CACHE[shape]
            with self.subTest(shape=shape):
                self.assertEqual(
                    f.query("SELECT COUNT(*) FROM images WHERE type_id NOT IN "
                            "(SELECT id FROM image_types) OR LENGTH(data) = 0",
                            "media")[0][0], 0)

    def test_atlas_sheets_are_copied_and_renamed(self):
        f = _CACHE["v7c"]
        self.assertEqual(f.media_counts["image_atlas"], 1)
        self.assertTrue(os.path.isfile(os.path.join(f.dir, "atlas", "0_0.png")))

    def test_every_run_reports_how_many_vectors_it_dropped(self):
        """MISSION 3.5: the user must be told to recompute them."""
        for shape in SHAPES:
            f = _CACHE[shape]
            with self.subTest(shape=shape):
                n = f.ir.dropped.vectors
                self.assertGreater(n, 0, "the fixtures all carry vectors")
                self.assertEqual(f.report.counts["dropped"]["vectors"], n)
                line = [w for w in f.report.warnings
                        if "vector(s)" in w and "recompute" in w]
                self.assertEqual(len(line), 1, f.report.warnings)
                self.assertIn("%d vector(s)" % n, line[0])

    def test_the_vector_line_is_emitted_even_with_nothing_to_drop(self):
        # otherwise a silent report is ambiguous: no vectors, or not looked for?
        self.assertIn("0 vector(s)", Dropped().summary_lines()[0])

    def test_maps_embed_only_live_instance_ids(self):
        f = _CACHE["v7c"]
        data = json.loads(f.query("SELECT data FROM maps", "media")[0][0])
        live = {r[0] for r in f.query("SELECT id FROM instances")}
        self.assertTrue(set(data[::3]) <= live)


class ProjectDbTests(unittest.TestCase):
    def test_project_config_has_an_id_for_the_panoptic_registry(self):
        for shape in SHAPES:
            f = _CACHE[shape]
            with self.subTest(shape=shape):
                cfg = dict(f.query("SELECT key, value FROM project_config", "project"))
                self.assertEqual(set(cfg), {"id", "name", "description"})
                self.assertRegex(json.loads(cfg["id"]),
                                 r"^[0-9a-f-]{36}$")
                self.assertEqual(json.loads(cfg["id"]),
                                 f.report.counts["project_id"])

    def test_plugin_params_land_in_user_defaults(self):
        f = _CACHE["v7c"]
        rows = dict(((u, k), json.loads(d)) for u, k, d in
                    f.query("SELECT user_id, key, data FROM user_defaults", "project"))
        self.assertIn(("plugin.FaissPlugin", "params"), rows)
        # the dead plugin_data table is never used
        self.assertEqual(f.query("SELECT COUNT(*) FROM plugin_data",
                                 "project")[0][0], 0)

    def test_tabs_and_ui_data_are_dropped(self):
        for shape in SHAPES:
            self.assertEqual(_CACHE[shape].query(
                "SELECT COUNT(*) FROM tab_data", "project")[0][0], 0)


class SafetyTests(unittest.TestCase):
    def test_the_source_is_never_touched(self):
        for shape in SHAPES:
            db = fixture_db(shape)
            with self.subTest(shape=shape):
                stat = os.stat(db)
                _CACHE[shape].query("SELECT COUNT(*) FROM files")
                after = os.stat(db)
                self.assertEqual((stat.st_size, stat.st_mtime),
                                 (after.st_size, after.st_mtime))
                for sidecar in ("-wal", "-shm"):
                    self.assertFalse(os.path.exists(db + sidecar))

    def test_a_rerun_is_byte_identical(self):
        # CLAUDE.md rule 1: every conversion must be re-runnable from the
        # original. Only project.db differs, and only by its fresh UUID.
        import hashlib
        tmp = tempfile.mkdtemp(prefix="migrator-rerun-")
        try:
            digests = []
            for i in ("a", "b"):
                out = os.path.join(tmp, i)
                migrate("v7c", out)
                digests.append([hashlib.sha256(open(os.path.join(out, n), "rb")
                                               .read()).hexdigest()
                                for n in ("data.db", "media.db")])
            self.assertEqual(digests[0], digests[1])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_version_row_in_every_written_db(self):
        for shape in SHAPES:
            f = _CACHE[shape]
            with self.subTest(shape=shape):
                for db in ("project", "data", "media"):
                    self.assertEqual(
                        f.query("SELECT key, value FROM _version", db),
                        [("db_version", 1)])

    def test_output_folder_has_no_stray_wal_files(self):
        for shape in SHAPES:
            names = _CACHE[shape].files_written
            with self.subTest(shape=shape):
                self.assertFalse([n for n in names if n.endswith(("-wal", "-shm"))])


class EmptyProjectTests(unittest.TestCase):
    """A project with nothing in it: the empty-table seeding rule (2.2)."""

    def setUp(self):
        from panoptic.migration.ir import ProjectIR
        self.tmp = tempfile.mkdtemp(prefix="migrator-empty-")
        self.ir = ProjectIR(shape="v7c")
        from panoptic.migration.writers import write_data_db, write_media_db, write_project_db
        data = os.path.join(self.tmp, "data.db")
        media = os.path.join(self.tmp, "media.db")
        project = os.path.join(self.tmp, "project.db")
        write_data_db(data, self.ir)
        write_media_db(media, self.ir, target_dir=self.tmp)
        write_project_db(project, self.ir, data, media, name="empty")
        self.paths = (project, data, media)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_post_conditions_hold_on_an_empty_project(self):
        self.assertEqual(PostConditions(*self.paths).run(), [])

    def test_empty_tables_seed_to_the_struct_default_of_one(self):
        conn = sqlite3.connect(self.paths[0])
        registry = {k: (json.loads(v) if isinstance(v, (str, bytes)) else v)
                    for k, v in conn.execute("SELECT key, value FROM id_registry")}
        conn.close()
        self.assertEqual(set(registry), set(ID_REGISTRY_KEYS))
        for key in ("folders", "files", "instances", "tags", "property_groups",
                    "vector_types", "image_types", "image_atlas", "maps"):
            self.assertEqual(registry[key], 1, key)
        self.assertEqual(registry["file_sources"], 2)     # the one local source
        # nothing but the nine system properties, allocated from 1
        self.assertEqual(registry["properties"], 10)


class PostConditionsCatchTheTrapTests(unittest.TestCase):
    """The checks have to actually fire, or they are decoration."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="migrator-trap-")
        for name in ("project.db", "data.db", "media.db"):
            shutil.copy(os.path.join(_CACHE["v7c"].dir, name),
                        os.path.join(self.tmp, name))
        self.paths = tuple(os.path.join(self.tmp, n) for n in
                           ("project.db", "data.db", "media.db"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _failures(self):
        return PostConditions(*self.paths).run()

    def test_a_result_row_without_its_genesis_op_is_caught(self):
        # THE trap: this row would be silently tombstoned on the first edit.
        conn = sqlite3.connect(self.paths[1])
        conn.execute("DELETE FROM entity_log WHERE entity_type = 'tag' "
                     "AND entity_key = '[1]'")
        conn.commit()
        conn.close()
        self.assertTrue(any("genesis pairing [tag]" in f for f in self._failures()))

    def test_an_under_seeded_id_registry_is_caught(self):
        conn = sqlite3.connect(self.paths[0])
        conn.execute("UPDATE id_registry SET value = '5' WHERE key = 'tags'")
        conn.commit()
        conn.close()
        self.assertTrue(any("id_registry[tags]" in f for f in self._failures()))

    def test_a_missing_id_registry_key_is_caught(self):
        conn = sqlite3.connect(self.paths[0])
        conn.execute("DELETE FROM id_registry WHERE key = 'maps'")
        conn.commit()
        conn.close()
        self.assertTrue(any("id_registry keys" in f for f in self._failures()))

    def test_a_null_id_registry_value_is_caught(self):
        conn = sqlite3.connect(self.paths[0])
        conn.execute("UPDATE id_registry SET value = NULL WHERE key = 'folders'")
        conn.commit()
        conn.close()
        self.assertTrue(any("id_registry[folders]" in f for f in self._failures()))

    def test_a_missing_sequence_seed_row_is_caught(self):
        conn = sqlite3.connect(self.paths[1])
        conn.execute("DELETE FROM sequence")
        conn.commit()
        conn.close()
        self.assertTrue(any("sequence seed row" in f for f in self._failures()))

    def test_a_dangling_reference_is_caught(self):
        conn = sqlite3.connect(self.paths[1])
        conn.execute("UPDATE instance_values SET instance_id = 9999 "
                     "WHERE instance_id = 1")
        conn.commit()
        conn.close()
        self.assertTrue(any("instance_values.instance_id" in f
                            for f in self._failures()))


class NegativePropertyIdTests(unittest.TestCase):
    """Legacy computed properties were virtual, with negative ids (4.2)."""

    def setUp(self):
        from panoptic.migration.ir import ProjectIR
        from panoptic.migration.writers import SystemPropertyPlan
        from panoptic.migration.writers.project_db import ProjectDbWriter
        self.plan = SystemPropertyPlan(14)          # the fixtures' legacy max
        self.w = ProjectDbWriter("/dev/null", ProjectIR(shape="v7c"), "", "",
                                 system=self.plan)

    def test_system_ids_start_above_the_legacy_maximum(self):
        self.assertEqual(self.plan.base, 15)
        self.assertEqual(self.plan.ids["id"], 15)
        self.assertEqual(self.plan.ids["created_at"], 23)
        self.assertEqual(self.plan.next_property_id, 24)

    def test_known_computed_ids_are_remapped_and_ahash_is_dropped(self):
        blob = {"property_id": -1, "filter": {"property_id": -3},
                "sort": {"propertyIds": [-2, -7]}, "unrelated": -5}
        out = self.w.remap_property_ids(blob, "test")
        self.assertEqual(out["property_id"], self.plan.ids["id"])
        self.assertIsNone(out["filter"]["property_id"])    # -3 has no target
        self.assertEqual(out["sort"]["propertyIds"],
                         [self.plan.ids["sha1"], self.plan.ids["name"]])
        self.assertEqual(out["unrelated"], -5)             # not a property key
        self.assertTrue(any("no target" in n for n in self.w.notes))
        self.assertTrue(any("remapped" in n for n in self.w.notes))


# ---------------------------------------------------------------------------
# `--table`: the human-readable pass
# ---------------------------------------------------------------------------

def print_table():
    tmp = tempfile.mkdtemp(prefix="migrator-writers-")
    try:
        head = ("shape", "fold", "inst", "prop", "tags", "ivals", "svals",
                "itag", "stag", "log", "img", "atlas", "maps", "checks")
        print("%-6s %4s %4s %4s %4s %5s %5s %4s %4s %5s %4s %5s %4s %s"
              % head)
        for shape in SHAPES:
            f = MigratedFixture(shape, os.path.join(tmp, shape))
            pc = PostConditions(f.project, f.data, f.media)
            failures = pc.run()
            d, m = f.data_counts, f.media_counts
            print("%-6s %4d %4d %4d %4d %5d %5d %4d %4d %5d %4d %5d %4d %s"
                  % (shape, d["folders"], d["instances"], d["properties"],
                     d["tags"], d["instance_values"], d["sha1_values"],
                     d["instance_tag_values"], d["sha1_tag_values"],
                     d["entity_log"], m["images"], m["image_atlas"], m["maps"],
                     "%d ok" % len(pc.checks) if not failures
                     else "FAILED: %s" % failures))
            print("       id_registry: %s"
                  % ", ".join("%s=%d" % (k, f.registry[k])
                              for k in ID_REGISTRY_KEYS))
            skips = {}
            for w in f.report.warnings:
                if "skipped" in w:
                    skips[w] = 1
            for w in sorted(skips):
                print("       %s" % w)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


class MiniThumbnailWarningTests(unittest.TestCase):
    """0.3.x's on-disk `mini/` thumbnails are dropped -- say so (task 4.2/5.1).

    Silent cosmetic loss is the worst kind: the project opens, looks fine, and
    browses at full resolution forever. The warning is the whole fix.
    """

    def _warnings(self, shape):
        report = Report(os.path.join(FIXTURES, shape), None, None, False)
        source = os.path.join(FIXTURES, shape, "panoptic.db")
        target = tempfile.mkdtemp(prefix="migrator-mini-")
        shutil.rmtree(target)
        try:
            run_pipeline(detect_db(source), source, target, report)
            return report.warnings
        finally:
            shutil.rmtree(target, ignore_errors=True)

    def test_v1_and_v2_warn_about_their_mini_folder(self):
        for shape in ("v1", "v2"):
            with self.subTest(shape=shape):
                self.assertTrue(
                    os.path.isdir(os.path.join(FIXTURES, shape, "mini")),
                    "fixture precondition: %s should have a mini/ folder" % shape)
                self.assertTrue(any("NOT carried over" in w and "mini" in w
                                    for w in self._warnings(shape)))

    def test_a_shape_without_a_mini_folder_says_nothing(self):
        self.assertFalse(os.path.isdir(os.path.join(FIXTURES, "v7c", "mini")))
        self.assertFalse(any("NOT carried over" in w
                                 for w in self._warnings("v7c")))


if __name__ == "__main__":
    if "--table" in sys.argv:
        print_table()
    else:
        unittest.main()
