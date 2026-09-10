"""Detector validation against the 11 real fixtures in ROOT/fixtures/.

Run it either way:
    python -m migrator.tests.test_detect      (from ROOT)
    python -m unittest migrator.tests.test_detect

Every fixture must be identified from sqlite_master alone. v3 and v4 are
schema-identical, so both land in the single `v3_v4` branch; the `variant`
field carries the (non-authoritative) data-derived v3/v4 hint.
"""

from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))   # panoptic_back/
if ROOT not in sys.path:  # allow running this file directly, not just as a module
    sys.path.insert(0, ROOT)

from panoptic.migration.detect import detect_db, sniff, SchemaFacts
from panoptic.migration.errors import UnknownShape

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

#: fixture folder -> (expected shape branch, expected variant hint)
EXPECTED = {
    "P0": ("P0", "P0"),
    "P1": ("P1", "P1"),
    "v1": ("v1", "v1"),
    "v2": ("v2", "v2"),
    "v3": ("v3_v4", "v3"),
    "v4": ("v3_v4", "v4"),
    "v5": ("v5", "v5"),
    "v6": ("v6", "v6"),
    "v7a": ("v7a", "v7a"),
    "v7b": ("v7b", "v7b"),
    "v7c": ("v7c", "v7c"),
}

class DetectFixtures(unittest.TestCase):
    def setUp(self):
        if not os.path.isdir(FIXTURES):
            self.skipTest("fixtures/ not present")

    def test_all_eleven_fixtures(self):
        seen = []
        for name, (shape, variant) in sorted(EXPECTED.items()):
            db = os.path.join(FIXTURES, name, "panoptic.db")
            with self.subTest(fixture=name):
                self.assertTrue(os.path.isfile(db), "missing fixture %s" % db)
                d = detect_db(db)
                self.assertEqual(d.shape, shape,
                                 "%s sniffed as %s" % (name, d.shape))
                self.assertEqual(d.variant, variant)
                seen.append(name)
        self.assertEqual(len(seen), 11)

    def test_source_is_never_modified(self):
        """Opening a fixture read-only must not change the file on disk."""
        db = os.path.join(FIXTURES, "v7c", "panoptic.db")
        before = (os.stat(db).st_mtime_ns, os.stat(db).st_size)
        detect_db(db)
        after = (os.stat(db).st_mtime_ns, os.stat(db).st_size)
        self.assertEqual(before, after)

    def test_recorded_version_is_only_a_crosscheck(self):
        """A v1 schema stamped `4` (the 0.4.x bug) still sniffs as v1."""
        facts = SchemaFacts(
            tables={"instances", "tabs", "plugin_defaults", "action_params",
                    "properties", "tags", "folders", "panoptic", "vectors",
                    "instance_property_values", "image_property_values"},
            recorded_db_version=4,
        )
        self.assertEqual(sniff(facts)[0], "v1")

    def test_unknown_shape_refused(self):
        with self.assertRaises(UnknownShape):
            sniff(SchemaFacts(tables={"sqlite_sequence", "something_else"}))
        with self.assertRaises(UnknownShape):
            sniff(SchemaFacts(tables=set()))


def print_table():
    """`--table`: show what the detector makes of every fixture."""
    print("%-6s %-7s %-7s %-8s %s" % ("fixture", "shape", "variant", "key", "ok"))
    ok = True
    for name, (shape, variant) in sorted(EXPECTED.items()):
        db = os.path.join(FIXTURES, name, "panoptic.db")
        d = detect_db(db)
        good = (d.shape, d.variant) == (shape, variant)
        ok = ok and good
        print("%-6s %-7s %-7s %-8s %s"
              % (name, d.shape, d.variant, d.facts.recorded_db_version,
                 "ok" if good else "MISMATCH expected %s/%s" % (shape, variant)))
    return 0 if ok else 1


if __name__ == "__main__":
    if "--table" in sys.argv:
        sys.exit(print_table())
    unittest.main(argv=["test_detect", "-v"])
