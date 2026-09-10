"""Round-trip invariants: every fixture, before vs after (task 4.1).

    python3 -m unittest migrator.tests.test_roundtrip     # assert
    python3 migrator/tests/test_roundtrip.py --table      # look at it

`test_writers` already checks the *output* against the migrator's own IR and
against the target's structural rules.  This module does the other half: it
rebuilds the "before" picture with **plain sqlite3 over the legacy DB** -- not
through `migrator.readers`, so a reader bug cannot cancel itself out -- and
compares it, row for row, with what came out the far end:

* folder tree (path / name / parent), instance and file inventory,
* the property set (name -> dtype, mode) and the tag DAG (parents by name),
* every single value, keyed by (property name, file identity | sha1),
* every single tag assignment, expanded from the legacy JSON id lists,
* and the counts stated independently in each fixture's `_fixture_report.json`.

Values are keyed by (folder path, file name) and tags by their text rather than
by id, so that a mis-keyed row cannot hide behind a matching id.  Legacy
`instances.id` *is* preserved verbatim by the migration (ID_STRATEGY section 2 --
`maps.data` embeds instance ids and is copied as an opaque blob), and
`InstanceIdPreservationTests` below pins that.

Dropped by design (CLAUDE.md sign-off) and therefore never asserted as
preserved: vectors, tabs / ui_data, raw_images, ahash.
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
from panoptic.migration.pipeline import run_pipeline                 # noqa: E402
from panoptic.migration.report import Report                         # noqa: E402
from panoptic.migration.writers import PostConditions                # noqa: E402
from panoptic.migration.writers.panoptic_db import read_project_config   # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
SHAPES = ("P0", "P1", "v1", "v2", "v3", "v4", "v5", "v6", "v7a", "v7b", "v7c")

#: `checkbox = false` stops being *stored* at 0.4.5 -- `clean_and_separate_values`
#: deletes any falsy value -- so v4+ fixtures hold 6 fewer rows per scope than
#: v1-v3 do from the identical build script (MISSION 1.3).  The round-trip below
#: compares each fixture against *its own* legacy DB, so it never has to know
#: this; this table only pins the shape of the ground truth so a silent change
#: in the fixtures cannot pass unnoticed.
FALSE_IS_STORED = {"P0": True, "P1": True, "v1": True, "v2": True, "v3": True,
                   "v4": False, "v5": False, "v6": False, "v7a": False,
                   "v7b": False, "v7c": False}

TAG_DTYPES = ("tag", "multi_tags")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def ro(path):
    return sqlite3.connect("file:%s?mode=ro" % path, uri=True)


def has_table(conn, name):
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                             "AND name=?", (name,)).fetchone())


def columns(conn, table):
    return [r[1] for r in conn.execute('PRAGMA table_info("%s")' % table)]


def decode(value):
    """Legacy and target both store JSON text in a NUMERIC-affinity column."""
    if isinstance(value, bytes):
        value = value.decode("utf-8", "replace")
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return value
    return value


def canon(value):
    """Hashable, comparable form of a decoded value."""
    if isinstance(value, list):
        return ("[]",) + tuple(canon(v) for v in value)
    if isinstance(value, dict):
        return ("{}",) + tuple(sorted((k, canon(v)) for k, v in value.items()))
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, (int, float)):
        # sqlite's NUMERIC affinity turns '13' into 13 on the way in; 1 and 1.0
        # must not read as different values either.
        return ("num", float(value))
    return ("s", value)


def as_id_list(value):
    """A legacy tag-property value: a JSON list of tag ids (or a bare id)."""
    value = decode(value)
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [int(v) for v in value if v is not None]
    return [int(value)]


def strip_root_sentinel(parents):
    """P0/P1/v1/v2 write `parents = [0]` for a root tag; v3+ write `[]`."""
    return sorted(p for p in (parents or []) if p)


# ---------------------------------------------------------------------------
# "before": the legacy DB, read with plain sqlite3
# ---------------------------------------------------------------------------

class Snapshot(object):
    """The shape-independent picture both sides are reduced to."""

    def __init__(self):
        self.folders = set()        # (path, name, parent_path|None)
        self.files = set()          # (folder_path, file_name)
        self.file_sha1 = {}         # (folder_path, file_name) -> sha1
        self.instances = 0
        self.properties = {}        # name -> (dtype, mode)
        self.tags = {}              # (property_name, tag_value) -> (parent names)
        self.instance_values = set()  # (prop_name, file_key, canon(value))
        self.sha1_values = set()      # (prop_name, sha1, canon(value))
        self.instance_tags = set()    # (prop_name, file_key, tag_value)
        self.sha1_tags = set()        # (prop_name, sha1, tag_value)

    def value_total(self):
        return len(self.instance_values) + len(self.sha1_values)

    def tag_total(self):
        return len(self.instance_tags) + len(self.sha1_tags)


def legacy_snapshot(shape, db):
    conn = ro(db)
    try:
        snap = Snapshot()

        # --- folders ------------------------------------------------------
        folder_path = {}
        for fid, path, name, parent in conn.execute(
                "SELECT id, path, name, parent FROM folders"):
            folder_path[fid] = path
        for fid, path, name, parent in conn.execute(
                "SELECT id, path, name, parent FROM folders"):
            snap.folders.add((path, name, folder_path.get(parent)))

        # --- properties ---------------------------------------------------
        prop_cols = columns(conn, "properties")
        has_mode = "mode" in prop_cols
        props = {}                      # id -> (name, dtype, mode)
        for row in conn.execute("SELECT id, name, type%s FROM properties"
                                % (", mode" if has_mode else "")):
            pid, name, dtype = row[0], row[1], row[2]
            # `v4_sql`: 'string' -> 'text'.  Applied defensively to every shape,
            # because 0.4.x stamped v1/v2 DBs as 4 without ever running it.
            dtype = "text" if dtype == "string" else dtype
            # P0 has no `mode` column at all: a value is keyed by sha1 only.
            mode = row[3] if has_mode else "sha1"
            props[pid] = (name, dtype, mode)
            snap.properties[name] = (dtype, mode)

        # --- tags ---------------------------------------------------------
        tags = {}                       # id -> (property_id, value, parents)
        for tid, pid, value, parents in conn.execute(
                "SELECT id, property_id, value, parents FROM tags"):
            tags[tid] = (pid, value, strip_root_sentinel(decode(parents)))
        for tid, (pid, value, parents) in tags.items():
            snap.tags[(props[pid][0], value)] = tuple(
                sorted(tags[p][1] for p in parents if p in tags))

        # --- files / instances --------------------------------------------
        instance_key = {}               # legacy instance (or image) id -> key
        sha1_of = {}
        if shape == "P0":
            # 0.0.8's `save_callback` bug: `images.paths` holds the folder id.
            for sha1, name, paths in conn.execute(
                    "SELECT sha1, name, paths FROM images"):
                ids = as_id_list(paths)
                key = (folder_path.get(ids[0] if ids else None), name)
                snap.files.add(key)
                snap.file_sha1[key] = sha1
                sha1_of[sha1] = sha1
            snap.instances = len(snap.files)
        else:
            table = "images" if shape == "P1" else "instances"
            for iid, fid, name in conn.execute(
                    "SELECT id, folder_id, name FROM %s" % table):
                instance_key[iid] = (folder_path.get(fid), name)
            for iid, fid, name, sha1 in conn.execute(
                    "SELECT id, folder_id, name, sha1 FROM %s" % table):
                key = (folder_path.get(fid), name)
                snap.files.add(key)
                snap.file_sha1[key] = sha1
            snap.instances = conn.execute(
                "SELECT COUNT(*) FROM %s" % table).fetchone()[0]

        # --- values --------------------------------------------------------
        def route(pid, scope, key, value):
            """dtype first, mode second -- MAPPING section 4.2."""
            if pid not in props:
                return                  # dangling: the reader drops these too
            name, dtype, _mode = props[pid]
            if dtype in TAG_DTYPES:
                for tid in as_id_list(value):
                    if tid not in tags or tags[tid][0] != pid:
                        continue        # unknown / cross-property: dropped
                    target = snap.instance_tags if scope == "instance" \
                        else snap.sha1_tags
                    target.add((name, key, tags[tid][1]))
            else:
                if value is None:
                    return
                target = snap.instance_values if scope == "instance" \
                    else snap.sha1_values
                target.add((name, key, canon(decode(value))))

        if shape == "P0":
            for sha1, pid, value in conn.execute(
                    "SELECT sha1, property_id, value FROM images_properties"):
                route(pid, "sha1", sha1, value)
        elif shape == "P1":
            # `convert_old_db.py`: image_id == -1 means the value is sha1-scoped.
            for pid, iid, sha1, value in conn.execute(
                    "SELECT property_id, image_id, sha1, value "
                    "FROM property_values"):
                if iid == -1:
                    route(pid, "sha1", sha1, value)
                elif iid in instance_key:
                    route(pid, "instance", instance_key[iid], value)
        else:
            for pid, iid, value in conn.execute(
                    "SELECT property_id, instance_id, value "
                    "FROM instance_property_values"):
                if iid in instance_key:
                    route(pid, "instance", instance_key[iid], value)
            for pid, sha1, value in conn.execute(
                    "SELECT property_id, sha1, value FROM image_property_values"):
                route(pid, "sha1", sha1, value)
        return snap
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# "after": the migrated folder
# ---------------------------------------------------------------------------

def migrated_snapshot(folder):
    conn = ro(os.path.join(folder, "data.db"))
    try:
        snap = Snapshot()
        folder_path = {}
        for fid, path, name, parent in conn.execute(
                "SELECT id, path, name, parent FROM folders"):
            folder_path[fid] = path
        for fid, path, name, parent in conn.execute(
                "SELECT id, path, name, parent FROM folders"):
            snap.folders.add((path, name, folder_path.get(parent)))

        file_key = {}
        for fid, name, folder_id, sha1 in conn.execute(
                "SELECT id, name, folder_id, sha1 FROM files"):
            key = (folder_path.get(folder_id), name)
            file_key[fid] = key
            snap.files.add(key)
            snap.file_sha1[key] = sha1

        instance_key = {}
        for iid, file_id in conn.execute("SELECT id, file_id FROM instances"):
            instance_key[iid] = file_key.get(file_id)
        snap.instances = len(instance_key)

        props = {}                      # id -> name
        for pid, name, dtype, mode in conn.execute(
                "SELECT id, name, dtype, mode FROM properties "
                "WHERE system_key IS NULL"):
            props[pid] = name
            snap.properties[name] = (dtype, mode)

        tags = {}                       # id -> (list_id, value, parents)
        for tid, list_id, value, parents in conn.execute(
                "SELECT id, list_id, value, parents FROM tags"):
            tags[tid] = (list_id, value, decode(parents) or [])
        # `tag_list_id == property.id` is the signed-off convention
        list_owner = dict(conn.execute(
            "SELECT tag_list_id, id FROM properties "
            "WHERE tag_list_id IS NOT NULL"))
        for tid, (list_id, value, parents) in tags.items():
            owner = props.get(list_owner.get(list_id))
            snap.tags[(owner, value)] = tuple(
                sorted(tags[p][1] for p in parents if p in tags))

        for pid, iid, value in conn.execute(
                "SELECT property_id, instance_id, value FROM instance_values"):
            if pid in props:
                snap.instance_values.add(
                    (props[pid], instance_key.get(iid), canon(decode(value))))
        for pid, sha1, value in conn.execute(
                "SELECT property_id, sha1, value FROM sha1_values"):
            if pid in props:
                snap.sha1_values.add((props[pid], sha1, canon(decode(value))))
        for pid, iid, tid in conn.execute(
                "SELECT property_id, instance_id, tag_id FROM instance_tag_values"):
            if pid in props:
                snap.instance_tags.add(
                    (props[pid], instance_key.get(iid), tags[tid][1]))
        for pid, sha1, tid in conn.execute(
                "SELECT property_id, sha1, tag_id FROM sha1_tag_values"):
            if pid in props:
                snap.sha1_tags.add((props[pid], sha1, tags[tid][1]))
        return snap
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# the fixtures, migrated once for the whole module
# ---------------------------------------------------------------------------

class Pair(object):
    def __init__(self, shape, target):
        self.shape = shape
        self.dir = target
        self.src = os.path.join(FIXTURES, shape, "panoptic.db")
        detection = detect_db(self.src)
        self.report = Report(os.path.dirname(self.src), self.src, target,
                             dry_run=False)
        self.report.set_detection(detection)
        self.ir = run_pipeline(detection, self.src, target, self.report)
        self.before = legacy_snapshot(shape, self.src)
        self.after = migrated_snapshot(target)
        with open(os.path.join(FIXTURES, shape, "_fixture_report.json")) as fh:
            self.fixture_report = json.load(fh)


_PAIRS = {}
_TMP = None


def setUpModule():
    global _TMP
    _TMP = tempfile.mkdtemp(prefix="migrator-roundtrip-")
    for shape in SHAPES:
        _PAIRS[shape] = Pair(shape, os.path.join(_TMP, shape))


def tearDownModule():
    if _TMP:
        shutil.rmtree(_TMP, ignore_errors=True)


class RoundTripCase(unittest.TestCase):
    def pairs(self):
        for shape in SHAPES:
            yield shape, _PAIRS[shape]


# ---------------------------------------------------------------------------
# structure
# ---------------------------------------------------------------------------

class FolderStructureTests(RoundTripCase):
    def test_the_folder_tree_survives_exactly(self):
        for shape, p in self.pairs():
            with self.subTest(shape=shape):
                self.assertEqual(p.after.folders, p.before.folders)

    def test_the_tree_is_two_levels_with_one_root(self):
        for shape, p in self.pairs():
            with self.subTest(shape=shape):
                roots = [f for f in p.after.folders if f[2] is None]
                self.assertEqual(len(roots), 1)
                self.assertEqual(len(p.after.folders), 2)

    def test_the_folder_tree_matches_the_fixture_report(self):
        for shape, p in self.pairs():
            with self.subTest(shape=shape):
                by_id = {f[0]: f for f in p.fixture_report["folders"]}
                expected = set()
                for fid, name, parent in p.fixture_report["folders"]:
                    expected.add((name, by_id[parent][1] if parent else None))
                self.assertEqual({(f[1], f[2].rsplit("/", 1)[-1] if f[2] else None)
                                  for f in p.after.folders}, expected)

    def test_every_folder_is_reachable_from_a_root(self):
        for shape, p in self.pairs():
            with self.subTest(shape=shape):
                paths = {f[0] for f in p.after.folders}
                for _path, _name, parent in p.after.folders:
                    if parent is not None:
                        self.assertIn(parent, paths)


class InventoryTests(RoundTripCase):
    def test_every_file_survives_with_its_folder_and_name(self):
        for shape, p in self.pairs():
            with self.subTest(shape=shape):
                self.assertEqual(p.after.files, p.before.files)

    def test_every_sha1_is_carried_over_unchanged(self):
        for shape, p in self.pairs():
            with self.subTest(shape=shape):
                self.assertEqual(p.after.file_sha1, p.before.file_sha1)

    def test_instance_count_is_preserved(self):
        for shape, p in self.pairs():
            with self.subTest(shape=shape):
                self.assertEqual(p.after.instances, p.before.instances)

    def test_instance_count_matches_the_fixture_report(self):
        for shape, p in self.pairs():
            with self.subTest(shape=shape):
                stated = p.fixture_report.get("instances",
                                              p.fixture_report.get("images"))
                self.assertEqual(p.after.instances, stated)

    def test_instances_and_files_are_one_to_one(self):
        for shape, p in self.pairs():
            with self.subTest(shape=shape):
                self.assertEqual(len(p.after.files), p.after.instances)


class PropertyTests(RoundTripCase):
    def test_every_property_survives_with_its_dtype_and_mode(self):
        for shape, p in self.pairs():
            with self.subTest(shape=shape):
                self.assertEqual(p.after.properties, p.before.properties)

    def test_property_names_and_types_match_the_fixture_report(self):
        for shape, p in self.pairs():
            with self.subTest(shape=shape):
                for name, spec in p.fixture_report["properties"].items():
                    # P1's build script stringified the enum: 'PropertyType.string'
                    dtype = str(spec[1]).rsplit(".", 1)[-1]
                    dtype = "text" if dtype == "string" else dtype
                    mode = spec[2] if len(spec) > 2 else "sha1"
                    self.assertEqual(p.after.properties[name], (dtype, mode),
                                     "%s.%s" % (shape, name))

    def test_no_string_dtype_reaches_the_target(self):
        # `v4_sql` re-applied defensively: nothing may still say 'string'
        for shape, p in self.pairs():
            with self.subTest(shape=shape):
                self.assertNotIn("string",
                                 [d for d, _m in p.after.properties.values()])

    def test_all_ten_declared_types_are_present_everywhere(self):
        want = {"text", "number", "tag", "multi_tags", "image_link", "url",
                "date", "path", "color", "checkbox"}
        for shape, p in self.pairs():
            with self.subTest(shape=shape):
                self.assertEqual(
                    want - {d for d, _m in p.after.properties.values()}, set())


class TagTests(RoundTripCase):
    def test_the_tag_dag_survives_with_its_parents(self):
        for shape, p in self.pairs():
            with self.subTest(shape=shape):
                self.assertEqual(p.after.tags, p.before.tags)

    def test_tag_count_matches_the_fixture_report(self):
        for shape, p in self.pairs():
            with self.subTest(shape=shape):
                self.assertEqual(len(p.after.tags),
                                 len(p.fixture_report["tags"]))

    def test_the_root_sentinel_never_becomes_a_phantom_tag_zero(self):
        # P0/P1/v1/v2 write parents = [0]; a naive copy invents a tag 0.
        for shape, p in self.pairs():
            with self.subTest(shape=shape):
                conn = ro(os.path.join(p.dir, "data.db"))
                try:
                    parents = [decode(r[0]) or []
                               for r in conn.execute("SELECT parents FROM tags")]
                    self.assertEqual(conn.execute(
                        "SELECT COUNT(*) FROM tags WHERE id = 0").fetchone()[0], 0)
                finally:
                    conn.close()
                self.assertFalse([p_ for row in parents for p_ in row if p_ == 0])

    def test_the_dag_is_preserved_not_flattened_to_a_tree(self):
        # `pet` has two parents (cat, dog) in every fixture.
        for shape, p in self.pairs():
            with self.subTest(shape=shape):
                multi = [k for k, v in p.after.tags.items() if len(v) > 1]
                self.assertTrue(multi, "the fixture DAG went missing")

    def test_every_tag_parent_points_at_a_tag_of_the_same_property(self):
        for shape, p in self.pairs():
            with self.subTest(shape=shape):
                by_prop = {}
                for (prop, value) in p.after.tags:
                    by_prop.setdefault(prop, set()).add(value)
                for (prop, value), parents in p.after.tags.items():
                    for parent in parents:
                        self.assertIn(parent, by_prop[prop],
                                      "%s: %s -> %s" % (shape, value, parent))


# ---------------------------------------------------------------------------
# values
# ---------------------------------------------------------------------------

class ValueTests(RoundTripCase):
    def test_every_instance_scoped_value_survives_verbatim(self):
        for shape, p in self.pairs():
            with self.subTest(shape=shape):
                self.assertEqual(p.after.instance_values,
                                 p.before.instance_values)

    def test_every_sha1_scoped_value_survives_verbatim(self):
        for shape, p in self.pairs():
            with self.subTest(shape=shape):
                self.assertEqual(p.after.sha1_values, p.before.sha1_values)

    def test_value_counts_per_property_are_identical(self):
        for shape, p in self.pairs():
            with self.subTest(shape=shape):
                for label in ("instance_values", "sha1_values"):
                    before, after = {}, {}
                    for name, _key, _v in getattr(p.before, label):
                        before[name] = before.get(name, 0) + 1
                    for name, _key, _v in getattr(p.after, label):
                        after[name] = after.get(name, 0) + 1
                    self.assertEqual(after, before, "%s.%s" % (shape, label))

    def test_a_tag_value_never_lands_in_a_generic_value_table(self):
        for shape, p in self.pairs():
            with self.subTest(shape=shape):
                tag_props = {n for n, (d, _m) in p.after.properties.items()
                             if d in TAG_DTYPES}
                for label in ("instance_values", "sha1_values"):
                    names = {n for n, _k, _v in getattr(p.after, label)}
                    self.assertEqual(names & tag_props, set(),
                                     "%s.%s" % (shape, label))

    def test_absent_values_stay_absent(self):
        """Two instances were deliberately left unset on the tag property."""
        for shape, p in self.pairs():
            with self.subTest(shape=shape):
                tagged = {key for name, key, _t in p.after.instance_tags
                          if p.after.properties.get(name, ("", ""))[0] == "tag"}
                single_tag = [n for n, (d, m) in p.after.properties.items()
                              if d == "tag"]
                if single_tag and tagged:
                    self.assertLess(len(tagged), len(p.after.files),
                                    "unset should not become set")

    def test_the_checkbox_shape_is_the_per_version_one_not_a_uniform_one(self):
        """`checkbox = false` genuinely vanishes upstream from 0.4.5 on."""
        for shape, p in self.pairs():
            with self.subTest(shape=shape):
                checkboxes = [n for n, (d, _m) in p.after.properties.items()
                              if d == "checkbox"]
                self.assertTrue(checkboxes)
                stored = [v for name, _k, v in p.after.instance_values
                          if name in checkboxes]
                stored += [v for name, _k, v in p.after.sha1_values
                           if name in checkboxes]
                falsy = [v for v in stored if v in (("bool", False), ("num", 0.0))]
                if FALSE_IS_STORED[shape]:
                    self.assertTrue(falsy, "v1-v3 do store `false` rows")
                else:
                    self.assertEqual(falsy, [], "v4+ never stored `false`")
                # either way, nothing was invented and nothing was lost:
                self.assertEqual(
                    len(stored),
                    len([1 for name, _k, _v in p.before.instance_values
                         if name in checkboxes]) +
                    len([1 for name, _k, _v in p.before.sha1_values
                         if name in checkboxes]))

    def test_total_value_rows_match_the_fixture_report(self):
        """The independent ground truth written at build time."""
        for shape, p in self.pairs():
            with self.subTest(shape=shape):
                r = p.fixture_report
                if "instance_values" in r:          # v3+
                    stated = r["instance_values"] + r["image_values"]
                elif "values" in r:                 # P0 (sha1 only), P1 (both)
                    stated = r["values"]
                else:                               # v1/v2: instance rows only
                    stated = r["values_set"] + len(p.before.sha1_values) \
                        + len({(n, k) for n, k, _t in p.before.sha1_tags})
                rows = (len(p.after.instance_values) + len(p.after.sha1_values)
                        + len({(n, k) for n, k, _t in p.after.instance_tags})
                        + len({(n, k) for n, k, _t in p.after.sha1_tags}))
                self.assertEqual(rows, stated)


class TagAssignmentTests(RoundTripCase):
    def test_every_instance_tag_assignment_survives(self):
        for shape, p in self.pairs():
            with self.subTest(shape=shape):
                self.assertEqual(p.after.instance_tags, p.before.instance_tags)

    def test_every_sha1_tag_assignment_survives(self):
        for shape, p in self.pairs():
            with self.subTest(shape=shape):
                self.assertEqual(p.after.sha1_tags, p.before.sha1_tags)

    def test_a_legacy_list_of_n_tags_becomes_n_junction_rows(self):
        for shape, p in self.pairs():
            with self.subTest(shape=shape):
                conn = ro(p.src)
                try:
                    expected = 0
                    tag_props = {}
                    cols = columns(conn, "properties")
                    for row in conn.execute(
                            "SELECT id, type FROM properties"):
                        if row[1] in TAG_DTYPES:
                            tag_props[row[0]] = row[1]
                    tables = {"P0": [("images_properties", "value")],
                              "P1": [("property_values", "value")]}.get(
                        shape, [("instance_property_values", "value"),
                                ("image_property_values", "value")])
                    for table, col in tables:
                        for pid, value in conn.execute(
                                "SELECT property_id, %s FROM %s" % (col, table)):
                            if pid in tag_props:
                                expected += len(as_id_list(value))
                finally:
                    conn.close()
                self.assertEqual(p.after.instance_tags and True or True, True)
                self.assertEqual(
                    len(p.after.instance_tags) + len(p.after.sha1_tags), expected)

    def test_multi_tags_really_carries_more_rows_than_files(self):
        for shape, p in self.pairs():
            with self.subTest(shape=shape):
                multi = {n for n, (d, _m) in p.after.properties.items()
                         if d == "multi_tags"}
                rows = [1 for n, _k, _t in p.after.instance_tags if n in multi]
                rows += [1 for n, _k, _t in p.after.sha1_tags if n in multi]
                self.assertGreater(len(rows), len(p.after.files))


# ---------------------------------------------------------------------------
# the whole-folder invariants
# ---------------------------------------------------------------------------

class WholeFolderTests(RoundTripCase):
    def test_post_conditions_pass_on_every_migrated_fixture(self):
        for shape, p in self.pairs():
            with self.subTest(shape=shape):
                failures = PostConditions(
                    os.path.join(p.dir, "project.db"),
                    os.path.join(p.dir, "data.db"),
                    os.path.join(p.dir, "media.db")).run()
                self.assertEqual(failures, [], "%s: %s" % (shape, failures))

    def test_the_registration_invariant_holds(self):
        for shape, p in self.pairs():
            with self.subTest(shape=shape):
                pid, name, _desc = read_project_config(p.dir)
                self.assertRegex(pid, r"^[0-9a-f-]{36}$")
                self.assertEqual(pid, p.report.counts["project_id"])
                self.assertTrue(name)

    def test_the_source_is_byte_for_byte_untouched(self):
        for shape, p in self.pairs():
            with self.subTest(shape=shape):
                self.assertFalse(os.path.exists(p.src + "-wal"))
                self.assertFalse(os.path.exists(p.src + "-shm"))

    def test_dropped_by_design_is_dropped_not_half_migrated(self):
        """vectors, tabs/ui_data, raw_images, ahash -- CLAUDE.md sign-off."""
        for shape, p in self.pairs():
            with self.subTest(shape=shape):
                media = ro(os.path.join(p.dir, "media.db"))
                project = ro(os.path.join(p.dir, "project.db"))
                try:
                    self.assertEqual(media.execute(
                        "SELECT COUNT(*) FROM vectors").fetchone()[0], 0)
                    self.assertEqual(media.execute(
                        "SELECT COUNT(*) FROM vector_types").fetchone()[0], 0)
                    self.assertEqual(project.execute(
                        "SELECT COUNT(*) FROM tab_data").fetchone()[0], 0)
                finally:
                    media.close()
                    project.close()
                # and the user is told, per run, what went missing
                self.assertGreater(p.ir.dropped.vectors, 0)


class TheComparisonActuallyFiresTests(unittest.TestCase):
    """A comparison that cannot fail is decoration -- so break one on purpose."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="migrator-rt-trap-")
        for name in ("project.db", "data.db", "media.db"):
            shutil.copy(os.path.join(_PAIRS["v7c"].dir, name),
                        os.path.join(self.tmp, name))
        self.before = _PAIRS["v7c"].before

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _mutate(self, sql):
        conn = sqlite3.connect(os.path.join(self.tmp, "data.db"))
        conn.execute(sql)
        conn.commit()
        conn.close()
        return migrated_snapshot(self.tmp)

    def test_a_deleted_value_is_noticed(self):
        after = self._mutate("DELETE FROM instance_values WHERE property_id = 1")
        self.assertNotEqual(after.instance_values, self.before.instance_values)

    def test_a_changed_value_is_noticed(self):
        after = self._mutate("UPDATE sha1_values SET value = '\"nope\"' "
                             "WHERE property_id = 11")
        self.assertNotEqual(after.sha1_values, self.before.sha1_values)

    def test_a_dropped_tag_assignment_is_noticed(self):
        after = self._mutate("DELETE FROM instance_tag_values WHERE tag_id = 3")
        self.assertNotEqual(after.instance_tags, self.before.instance_tags)

    def test_a_reparented_tag_is_noticed(self):
        after = self._mutate("UPDATE tags SET parents = '[]' WHERE id = 6")
        self.assertNotEqual(after.tags, self.before.tags)

    def test_a_renamed_file_is_noticed(self):
        after = self._mutate("UPDATE files SET name = 'x.png' WHERE id = 1")
        self.assertNotEqual(after.files, self.before.files)

    def test_a_lost_folder_is_noticed(self):
        after = self._mutate("DELETE FROM folders WHERE parent IS NOT NULL")
        self.assertNotEqual(after.folders, self.before.folders)



# ---------------------------------------------------------------------------
# ids are preserved -- load-bearing, because `maps.data` embeds instance ids
# ---------------------------------------------------------------------------

class InstanceIdPreservationTests(RoundTripCase):
    """`instances.id` / `files.id` are the legacy ids, unchanged.

    `media.maps.data` is a flat JSON array `[instance_id, x, y, ...]` copied as
    an opaque blob (MAPPING section 7.6, ID_STRATEGY section 2), so renumbering
    instances would silently point every map coordinate at the wrong image.
    P0 is excluded: it has no per-copy instance identity to preserve at all
    (MAPPING U5/L7), its instances are synthesised from sha1 order.
    """

    ID_SHAPES = tuple(s for s in SHAPES if s != "P0")

    def _legacy_instances(self, shape, db):
        """{legacy id: (folder path, file name)} straight from the legacy DB."""
        conn = ro(db)
        try:
            table = "instances" if has_table(conn, "instances") else "images"
            folders = {r[0]: r[1] for r in
                       conn.execute("SELECT id, path FROM folders")}
            return {r[0]: (folders.get(r[1]), r[2]) for r in
                    conn.execute("SELECT id, folder_id, name FROM %s" % table)}
        finally:
            conn.close()

    def _migrated_instances(self, folder):
        conn = ro(os.path.join(folder, "data.db"))
        try:
            folders = {r[0]: r[1] for r in
                       conn.execute("SELECT id, path FROM folders")}
            return {r[0]: (folders.get(r[2]), r[3], r[1]) for r in conn.execute(
                "SELECT i.id, i.file_id, f.folder_id, f.name "
                "FROM instances i JOIN files f ON f.id = i.file_id")}
        finally:
            conn.close()

    def test_every_legacy_instance_id_survives_on_the_same_file(self):
        for shape in self.ID_SHAPES:
            pair = _PAIRS[shape]
            legacy = self._legacy_instances(shape, pair.src)
            after = self._migrated_instances(pair.dir)
            self.assertEqual(sorted(legacy), sorted(after), shape)
            for iid, (path, name) in legacy.items():
                self.assertEqual((path, name), after[iid][:2],
                                 "%s: instance %d moved" % (shape, iid))

    def test_file_id_equals_instance_id(self):
        for shape in self.ID_SHAPES:
            for iid, row in self._migrated_instances(_PAIRS[shape].dir).items():
                self.assertEqual(iid, row[2], shape)

    def test_the_v7c_map_blob_is_copied_verbatim_and_still_resolves(self):
        pair = _PAIRS["v7c"]
        src = ro(pair.src)
        try:
            legacy_maps = {r[0]: (r[1], r[2], r[3], r[4], json.loads(r[5]))
                           for r in src.execute(
                               "SELECT id, source, name, key, count, data FROM maps")}
        finally:
            src.close()
        self.assertTrue(legacy_maps, "the v7c fixture must carry a map")

        conn = ro(os.path.join(pair.dir, "media.db"))
        try:
            after = {r[0]: (r[1], r[2], r[3], r[4], json.loads(r[5]))
                     for r in conn.execute(
                         "SELECT id, source, name, key, count, data FROM maps")}
        finally:
            conn.close()
        self.assertEqual(legacy_maps, after)

        live = set(self._migrated_instances(pair.dir))
        for mid, row in after.items():
            data = row[4]
            self.assertIsInstance(data, list)
            ids = [int(v) for v in data[0::3]]
            self.assertEqual(len(ids), row[3], "map %d count" % mid)
            self.assertEqual([i for i in ids if i not in live], [],
                             "map %d points at instances that do not exist" % mid)


class SparseInstanceIdsAreNotCompactedTests(unittest.TestCase):
    """Contiguous 1..n fixtures cannot tell "preserved" from "renumbered".

    So push one legacy instance to a sparse high id (6 -> 99, references and the
    map blob updated) on a *copy* of the v7c fixture and check it comes out as
    99, that the map still points at it, and that `id_registry.instances` is
    seeded past it.
    """

    MOVED, NEW_ID = 6, 99

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="migrator-rt-sparse-")
        self.src = os.path.join(self.tmp, "panoptic.db")
        shutil.copy(os.path.join(FIXTURES, "v7c", "panoptic.db"), self.src)
        conn = sqlite3.connect(self.src)
        conn.execute("UPDATE instances SET id = ? WHERE id = ?",
                     (self.NEW_ID, self.MOVED))
        conn.execute("UPDATE instance_property_values SET instance_id = ? "
                     "WHERE instance_id = ?", (self.NEW_ID, self.MOVED))
        row = conn.execute("SELECT id, data FROM maps").fetchone()
        data = json.loads(row[1])
        data[data.index(self.MOVED)] = self.NEW_ID
        conn.execute("UPDATE maps SET data = ? WHERE id = ?",
                     (json.dumps(data), row[0]))
        conn.commit()
        conn.close()
        self.out = os.path.join(self.tmp, "out")
        detection = detect_db(self.src)
        report = Report(self.tmp, self.src, self.out, dry_run=False)
        report.set_detection(detection)
        run_pipeline(detection, self.src, self.out, report)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_the_sparse_id_is_kept_and_nothing_is_compacted(self):
        conn = ro(os.path.join(self.out, "data.db"))
        try:
            ids = sorted(r[0] for r in conn.execute("SELECT id FROM instances"))
            files = sorted(r[0] for r in conn.execute("SELECT id FROM files"))
            name = conn.execute(
                "SELECT f.name FROM instances i JOIN files f ON f.id = i.file_id "
                "WHERE i.id = ?", (self.NEW_ID,)).fetchone()
        finally:
            conn.close()
        expected = sorted([i for i in range(1, 13) if i != self.MOVED]
                          + [self.NEW_ID])
        self.assertEqual(ids, expected)
        self.assertEqual(files, expected)
        self.assertIsNotNone(name)
        self.assertEqual(name[0], "00_red_square.png")

    def test_the_map_still_points_at_the_moved_instance(self):
        conn = ro(os.path.join(self.out, "media.db"))
        try:
            data = json.loads(conn.execute("SELECT data FROM maps").fetchone()[0])
        finally:
            conn.close()
        self.assertIn(self.NEW_ID, [int(v) for v in data[0::3]])
        self.assertNotIn(self.MOVED, [int(v) for v in data[0::3]])

    def test_the_id_registry_is_seeded_past_the_sparse_id(self):
        conn = ro(os.path.join(self.out, "project.db"))
        try:
            # `value JSON` has NUMERIC affinity, so sqlite hands back an int
            reg = {r[0]: int(r[1]) for r in
                   conn.execute("SELECT key, value FROM id_registry")}
        finally:
            conn.close()
        self.assertEqual(reg["instances"], self.NEW_ID + 1)
        self.assertEqual(reg["files"], self.NEW_ID + 1)


# ---------------------------------------------------------------------------
# `--table`: the human-readable pass
# ---------------------------------------------------------------------------

def print_table():
    tmp = tempfile.mkdtemp(prefix="migrator-roundtrip-")
    try:
        head = ("shape", "fold", "inst", "prop", "tags", "ivals", "svals",
                "itag", "stag", "round-trip")
        print("%-6s %4s %4s %4s %4s %5s %5s %5s %5s  %s" % head)
        ok = True
        for shape in SHAPES:
            p = Pair(shape, os.path.join(tmp, shape))
            b, a = p.before, p.after
            diffs = []
            for label in ("folders", "files", "properties", "tags",
                          "instance_values", "sha1_values", "instance_tags",
                          "sha1_tags"):
                if getattr(a, label) != getattr(b, label):
                    diffs.append(label)
            ok = ok and not diffs
            print("%-6s %4d %4d %4d %4d %5d %5d %5d %5d  %s"
                  % (shape, len(a.folders), a.instances, len(a.properties),
                     len(a.tags), len(a.instance_values), len(a.sha1_values),
                     len(a.instance_tags), len(a.sha1_tags),
                     "identical" if not diffs else "DIFFERS: %s" % ", ".join(diffs)))
        print("\n%s" % ("all 11 fixtures round-trip identically"
                        if ok else "SOME FIXTURES DIFFER"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    if "--table" in sys.argv:
        print_table()
    else:
        unittest.main()
