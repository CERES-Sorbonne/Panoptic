"""Read all 11 fixtures into the IR and cross-check them against their own
`_fixture_report.json` / `CONTENT.md`.

Two ways to run it, both from the repo root:

    python3 migrator/tests/test_readers.py --table     # printed summary per shape
    python3 -m unittest migrator.tests.test_readers    # asserted

The table is the human-readable artefact task 3.2 owes; the unittest is what
keeps it honest afterwards.
"""

from __future__ import annotations

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))   # panoptic_back/
if ROOT not in sys.path:  # allow running this file directly, not just as a module
    sys.path.insert(0, ROOT)

from panoptic.migration import legacy                                   # noqa: E402
from panoptic.migration.detect import detect_db                         # noqa: E402
from panoptic.migration.readers import READERS, read_source             # noqa: E402
from panoptic.migration.readers.base import normalise_dtype, normalise_parents  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
SHAPES = ("P0", "P1", "v1", "v2", "v3", "v4", "v5", "v6", "v7a", "v7b", "v7c")


def fixture_db(name):
    return os.path.join(FIXTURES, name, "panoptic.db")


def fixture_report(name):
    path = os.path.join(FIXTURES, name, "_fixture_report.json")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def expected_value_rows(rep):
    """What a fixture report says about value counts, normalised.

    The reports are not uniform: v3+ record `instance_values` + `image_values`,
    P0/P1 record a single `values` total, and v1/v2 record `values_set`, which
    is the **instance-scoped rows only**. Returns `(scope, count)` where scope
    is 'all' or 'instance'.
    """
    if "instance_values" in rep:
        return "all", rep["instance_values"] + rep["image_values"]
    if "values" in rep:
        return "all", rep["values"]
    return "instance", rep["values_set"]


def ir_value_rows(ir, scope):
    """Count *source* rows in the IR: a tag row counts once, not once per tag."""
    n = len(ir.instance_values)
    n += len({(i, p) for i, p, _ in ir.instance_tag_values})
    if scope == "all":
        n += len(ir.sha1_values)
        n += len({(s, p) for s, p, _ in ir.sha1_tag_values})
    return n


def read_fixture(name, stat_files=True):
    db = fixture_db(name)
    return read_source(detect_db(db), db, stat_files=stat_files)


class ReadAllFixtures(unittest.TestCase):
    """One IR per fixture, cross-checked against that fixture's own report."""

    @classmethod
    def setUpClass(cls):
        cls.irs = {name: read_fixture(name) for name in SHAPES}
        cls.reports = {name: fixture_report(name) for name in SHAPES}

    def test_every_sniffable_shape_has_a_reader(self):
        from panoptic.migration.detect import EXPECTED_DB_VERSION
        self.assertEqual(set(READERS), set(EXPECTED_DB_VERSION))

    def test_counts_match_the_fixture_report(self):
        for name in SHAPES:
            ir, rep = self.irs[name], self.reports[name]
            with self.subTest(shape=name):
                expected_instances = rep.get("instances", rep.get("images"))
                self.assertEqual(len(ir.instances), expected_instances)
                self.assertEqual(len(ir.folders), len(rep["folders"]))
                self.assertEqual(len(ir.properties), len(rep["properties"]))
                self.assertEqual(len(ir.tags), len(rep["tags"]))

    def test_folder_tree_matches(self):
        for name in SHAPES:
            ir, rep = self.irs[name], self.reports[name]
            with self.subTest(shape=name):
                got = sorted((f.id, f.name, f.parent) for f in ir.folders)
                want = sorted(tuple(f) for f in rep["folders"])
                self.assertEqual(got, want)

    def test_tag_hierarchy_matches_with_the_root_sentinel_normalised(self):
        """The fixture report records P0/P1/v1/v2 root tags as `[0]`; the IR
        must have turned that into `[]` (MAPPING U4) and nothing else."""
        for name in SHAPES:
            ir, rep = self.irs[name], self.reports[name]
            with self.subTest(shape=name):
                by_id = {t.id: t for t in ir.tags}
                for value, (tag_id, parents) in rep["tags"].items():
                    tag = by_id[tag_id]
                    self.assertEqual(tag.value, value)
                    self.assertEqual(tag.parents, [p for p in parents if p != 0])

    def test_no_phantom_tag_zero_anywhere(self):
        for name in SHAPES:
            with self.subTest(shape=name):
                for tag in self.irs[name].tags:
                    self.assertNotIn(0, tag.parents)

    def test_property_dtype_never_says_string(self):
        """`v4_sql` applied defensively: no shape reaches the IR with 'string'."""
        for name in SHAPES:
            with self.subTest(shape=name):
                dtypes = {p.dtype for p in self.irs[name].properties}
                self.assertNotIn("string", dtypes)

    def test_property_ids_and_modes_match_the_fixture_report(self):
        for name in SHAPES:
            ir, rep = self.irs[name], self.reports[name]
            with self.subTest(shape=name):
                by_id = {p.id: p for p in ir.properties}
                for pname, spec in rep["properties"].items():
                    prop = by_id[spec[0]]
                    self.assertEqual(prop.name, pname)
                    # P1's report writes the enum repr, e.g. 'PropertyType.string'
                    want = spec[1].split(".")[-1]
                    self.assertEqual(prop.dtype, normalise_dtype(want))
                    if len(spec) > 2:                      # P1+ record the mode
                        self.assertEqual(prop.mode, spec[2])
                    else:                                  # P0 has no mode column
                        self.assertEqual(prop.mode, "sha1")

    def test_total_value_count_matches_the_fixture_report(self):
        """Every legacy value row lands in exactly one of the four IR lists.

        Tag rows fan out (one JSON list -> N junction rows), so the comparison
        is on *source rows*: a tag-valued row counts once no matter how many
        tags it held.
        """
        for name in SHAPES:
            ir, rep = self.irs[name], self.reports[name]
            with self.subTest(shape=name):
                scope, want = expected_value_rows(rep)
                self.assertEqual(ir_value_rows(ir, scope), want)

    def test_tag_values_never_land_in_the_generic_value_lists(self):
        """MAPPING §4.2's trap: routing is on dtype first, mode second."""
        for name in SHAPES:
            ir = self.irs[name]
            with self.subTest(shape=name):
                tag_props = {p.id for p in ir.properties if p.is_tag}
                for v in ir.instance_values + ir.sha1_values:
                    self.assertNotIn(v.property_id, tag_props)

    def test_value_scope_follows_the_property_mode(self):
        for name in SHAPES:
            ir = self.irs[name]
            with self.subTest(shape=name):
                by_id = {p.id: p for p in ir.properties}
                for v in ir.instance_values:
                    self.assertEqual(by_id[v.property_id].mode, "id")
                    self.assertIsInstance(v.key, int)
                for v in ir.sha1_values:
                    self.assertEqual(by_id[v.property_id].mode, "sha1")
                    self.assertIsInstance(v.key, str)

    def test_instance_urls_are_filesystem_paths(self):
        """P0/P1 store `/images/<abspath>`; the IR must hold `<abspath>`."""
        for name in SHAPES:
            with self.subTest(shape=name):
                for inst in self.irs[name].instances:
                    self.assertFalse(inst.url.startswith("/images/"), inst.url)
                    self.assertTrue(os.path.isabs(inst.url), inst.url)

    def test_p0_folder_ids_come_from_the_paths_column(self):
        """P0's only file->folder link is the folder id inside `images.paths`."""
        ir = self.irs["P0"]
        folder_ids = {f.id for f in ir.folders}
        for inst in ir.instances:
            self.assertIn(inst.folder_id, folder_ids)
        # the fixture has 10 images in the root and 2 in `sub/`
        self.assertEqual(sorted(i.folder_id for i in ir.instances).count(2), 2)

    def test_p0_invents_one_instance_per_sha1(self):
        ir = self.irs["P0"]
        self.assertEqual(len({i.sha1 for i in ir.instances}), len(ir.instances))
        self.assertEqual(sorted(i.id for i in ir.instances),
                         list(range(1, len(ir.instances) + 1)))

    def test_v7b_project_params_are_empty_and_warned_about(self):
        ir = self.irs["v7b"]
        self.assertEqual(ir.project_params, {})
        self.assertTrue(any("_project" in w for w in ir.warnings), ir.warnings)

    def test_thumbnail_sizes_survive_where_the_shape_has_them(self):
        """The `project` kv is where 3.5 gets its `image_types` from.

        v3-v6 carry panoptic's own creation-time defaults (the fixture script
        could not set them -- `ProjectDb` had no `set_project_settings` before
        0.6, recorded as FAILED in those reports), while v7a/v7c carry the
        fixture's own 96/320/900. Both are real data and both must survive.
        """
        for name in ("v3", "v4", "v5", "v6"):
            with self.subTest(shape=name):
                params = self.irs[name].project_params
                self.assertEqual([params["image_small_size"],
                                  params["image_medium_size"],
                                  params["image_large_size"]], [128, 256, 1024])
        for name in ("v7a", "v7c"):
            with self.subTest(shape=name):
                params = self.irs[name].project_params
                self.assertEqual([params["image_small_size"],
                                  params["image_medium_size"],
                                  params["image_large_size"]], [96, 320, 900])
        for name in ("v3", "v4", "v5", "v6", "v7a", "v7c"):
            self.assertIs(self.irs[name].project_params["save_image_large"],
                          False, name)
        # No `project` table at all before v3; v7b's `_project` is always empty.
        for name in ("P0", "P1", "v1", "v2", "v7b"):
            self.assertEqual(self.irs[name].project_params, {}, name)

    def test_media_tables_only_where_the_shape_has_them(self):
        for name in SHAPES:
            ir = self.irs[name]
            with self.subTest(shape=name):
                has_thumbs = name in ("v3", "v4", "v5", "v6", "v7a", "v7b", "v7c")
                self.assertEqual(bool(ir.thumbnails), has_thumbs)
                self.assertEqual(len(ir.atlas), 1 if name == "v7c" else 0)
                self.assertEqual(len(ir.maps), 1 if name == "v7c" else 0)

    def test_plugin_params_are_carried(self):
        for name in ("v2", "v3", "v4", "v5", "v6", "v7a", "v7b", "v7c"):
            with self.subTest(shape=name):
                self.assertEqual(set(self.irs[name].plugin_params),
                                 {"FaissPlugin", "DummyPlugin"})
                self.assertEqual(self.irs[name].orphan_plugin_data, {})
        # v1 has no `plugin_data`; its params live in `plugin_defaults`, which
        # upstream dropped at v2 with no migration (MAPPING U2).
        self.assertIn("FaissPlugin", self.irs["v1"].plugin_params)

    def test_dropped_things_are_counted_not_carried(self):
        for name in SHAPES:
            ir = self.irs[name]
            with self.subTest(shape=name):
                self.assertEqual(ir.dropped.tabs, 2, "2 saved tabs per fixture")
                self.assertEqual(ir.dropped.vectors, 12, "12 vectors per fixture")
                self.assertEqual(ir.dropped.ahash, 12)
                self.assertEqual(ir.dropped.raw_images, 0)
        # v1 is the only shape with `action_params` (L8): dumped, not binned.
        self.assertIn("get_vectors", self.irs["v1"].dropped.action_params)
        # `default_vector` exists v2-v6 and is gone from v7a on (L9).
        self.assertIsNotNone(self.irs["v5"].dropped.default_vector)
        self.assertIsNone(self.irs["v7c"].dropped.default_vector)

    def test_created_at_comes_from_file_stats(self):
        """CLAUDE.md L11: default behaviour, not a flag."""
        ir = self.irs["v7c"]
        self.assertTrue(all(i.created_at for i in ir.instances))
        self.assertRegex(ir.instances[0].created_at,
                         r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d$")
        self.assertTrue(all(i.created_at is None
                            for i in read_fixture("v7c", stat_files=False).instances))

    def test_checkbox_false_loss_is_visible_and_not_papered_over(self):
        """L5: 118/48 rows at v1-v3, 112/42 from v4. Migrate what exists."""
        v3, v4 = self.irs["v3"], self.irs["v4"]
        self.assertEqual((len(v3.instance_values), len(v3.sha1_values)), (96, 36))
        self.assertEqual((len(v4.instance_values), len(v4.sha1_values)), (90, 30))
        # exactly the 6 + 6 `checkbox = false` rows `clean_and_separate_values`
        # deleted at 0.4.5; nothing synthesises them back (L5).
        self.assertEqual(len(v3.instance_values) - len(v4.instance_values), 6)
        self.assertEqual(len(v3.sha1_values) - len(v4.sha1_values), 6)

    def test_ids_are_preserved_from_v1_on(self):
        """Legacy folder/instance/property/tag ids survive (MAPPING "not lost")."""
        base = self.irs["v7c"]
        for name in ("v1", "v2", "v3", "v4", "v5", "v6", "v7a", "v7b"):
            with self.subTest(shape=name):
                self.assertEqual(sorted(i.id for i in self.irs[name].instances),
                                 sorted(i.id for i in base.instances))
                self.assertEqual(sorted(t.id for t in self.irs[name].tags),
                                 sorted(t.id for t in base.tags))

    def test_max_ids_are_reported_for_id_registry_seeding(self):
        m = self.irs["v7c"].max_ids()
        self.assertEqual(m["instances"], m["files"])
        self.assertEqual(m["properties"], 14)
        self.assertEqual(m["tags"], 10)
        self.assertEqual(m["image_atlas"], 0)   # legacy atlas id 0 is real

    def test_source_is_never_written(self):
        stats = {n: os.stat(fixture_db(n)) for n in SHAPES}
        for name in SHAPES:
            read_fixture(name)
        for name in SHAPES:
            after = os.stat(fixture_db(name))
            self.assertEqual((after.st_size, after.st_mtime),
                             (stats[name].st_size, stats[name].st_mtime), name)


class UpstreamChainStillSaysWhatWeThinkItSays(unittest.TestCase):
    """The copies in `migrator/legacy/` are the authority; keep us in sync."""

    def test_v4_is_the_only_value_changing_step(self):
        self.assertEqual(legacy.v4_sql,
                         'UPDATE properties SET type = "text" WHERE type="string";')
        self.assertEqual(normalise_dtype("string"), "text")
        self.assertEqual(normalise_dtype("text"), "text")
        self.assertEqual(normalise_dtype("multi_tags"), "multi_tags")

    def test_v7_still_destroys_vectors_so_we_still_must_not_run_it(self):
        self.assertIn("DROP TABLE IF EXISTS vectors", legacy.v7_sql)

    def test_root_sentinel_normaliser(self):
        self.assertEqual(normalise_parents("[0]"), [])
        self.assertEqual(normalise_parents("[]"), [])
        self.assertEqual(normalise_parents(None), [])
        self.assertEqual(normalise_parents("[3, 4]"), [3, 4])
        self.assertEqual(normalise_parents("[0, 3]"), [3])
        self.assertEqual(normalise_parents("not json"), [])


# --------------------------------------------------------------------------
# `--table`: the human-readable per-shape summary
# --------------------------------------------------------------------------

COLUMNS = ("folders", "instances", "properties", "tags", "property_groups",
           "instance_values", "sha1_values", "instance_tag_values",
           "sha1_tag_values", "thumbnails", "atlas", "maps")


def print_table():
    irs = {}
    for name in SHAPES:
        irs[name] = read_fixture(name)

    head = "%-6s" % "shape" + "".join("%8s" % c[:7] for c in COLUMNS)
    print(head)
    print("-" * len(head))
    for name in SHAPES:
        c = irs[name].counts()
        print("%-6s" % name + "".join("%8d" % c[col] for col in COLUMNS))

    print("\ndropped (counts only -- payloads never enter the IR):")
    print("%-6s%8s%9s%11s%8s%16s" % ("shape", "tabs", "vectors", "raw_images",
                                     "ahash", "default_vector"))
    for name in SHAPES:
        d = irs[name].dropped
        print("%-6s%8d%9d%11d%8d%16s"
              % (name, d.tabs, d.vectors, d.raw_images, d.ahash,
                 d.default_vector or "-"))

    print("\nwarnings:")
    for name in SHAPES:
        for w in irs[name].warnings:
            print("  %-5s %s" % (name, w))

    print("\ncross-check vs each fixture's _fixture_report.json:")
    ok = True
    for name in SHAPES:
        ir, rep = irs[name], fixture_report(name)
        want_inst = rep.get("instances", rep.get("images"))
        scope, want_vals = expected_value_rows(rep)
        got_vals = ir_value_rows(ir, scope)
        checks = [
            ("instances", len(ir.instances), want_inst),
            ("folders", len(ir.folders), len(rep["folders"])),
            ("properties", len(ir.properties), len(rep["properties"])),
            ("tags", len(ir.tags), len(rep["tags"])),
            ("value rows (%s)" % scope, got_vals, want_vals),
        ]
        bad = [(k, g, w) for k, g, w in checks if g != w]
        ok = ok and not bad
        print("  %-5s %s" % (name, "OK" if not bad else "MISMATCH " + repr(bad)))
    print("\n%s" % ("all 11 fixtures reconcile." if ok else "DISCREPANCIES FOUND."))
    return 0 if ok else 1


if __name__ == "__main__":
    if "--table" in sys.argv:
        raise SystemExit(print_table())
    unittest.main()
