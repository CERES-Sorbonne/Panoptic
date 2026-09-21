"""v7 vectors are carried over byte for byte; older shapes drop theirs (task 3.5).

    python3 -m unittest panoptic.migration.tests.test_vectors

User decision (2026-09-19): keep vectors for v7a/v7b/v7c only. Every assertion
here compares the OUTPUT media.db against the legacy SOURCE, never against the
writer's own bookkeeping.
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

from panoptic.migration.cli import build_parser                       # noqa: E402
from panoptic.migration.detect import detect_db                       # noqa: E402
from panoptic.migration.pipeline import run_pipeline                  # noqa: E402
from panoptic.migration.readers import iter_legacy_vectors            # noqa: E402
from panoptic.migration.report import Report                          # noqa: E402
from panoptic.migration.writers import PostConditions                 # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
V7 = ("v7a", "v7b", "v7c")


def ro(path):
    return sqlite3.connect("file:%s?mode=ro" % path, uri=True)


def migrate(db, target, **kw):
    detection = detect_db(db)
    report = Report(os.path.dirname(db), db, target, dry_run=False)
    report.set_detection(detection)
    ir = run_pipeline(detection, db, target, report, **kw)
    return ir, report


def rows(path, sql):
    conn = ro(path)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


class _TmpCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="migrator-vectors-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class V7RoundTripTests(_TmpCase):
    def test_types_and_vectors_are_byte_identical(self):
        for shape in V7:
            with self.subTest(shape=shape):
                src = os.path.join(FIXTURES, shape, "panoptic.db")
                out = os.path.join(self.tmp, shape)
                ir, report = migrate(src, out)
                media = os.path.join(out, "media.db")

                legacy_v = rows(src, "SELECT type_id, sha1, data FROM vectors "
                                     "ORDER BY 1, 2")
                new_v = rows(media, "SELECT type_id, sha1, data FROM vectors "
                                    "ORDER BY 1, 2")
                self.assertEqual(len(legacy_v), 12)
                self.assertEqual(new_v, legacy_v)          # bytes included
                self.assertTrue(all(isinstance(r[2], bytes) for r in new_v))
                self.assertEqual(rows(media, "SELECT DISTINCT typeof(data) "
                                             "FROM vectors"), [("blob",)])

                legacy_t = rows(src, "SELECT id, source, params FROM vector_type "
                                     "ORDER BY id")
                new_t = rows(media, "SELECT id, source, params FROM vector_types "
                                    "ORDER BY id")
                self.assertEqual([(i, s, json.loads(p)) for i, s, p in new_t],
                                 [(i, s, json.loads(p)) for i, s, p in legacy_t])
                # serialised exactly as the target's EntitySchema would
                self.assertEqual([p for _, _, p in new_t],
                                 [json.dumps(json.loads(p)) for _, _, p in legacy_t])

                reg = dict(rows(os.path.join(out, "project.db"),
                                "SELECT key, value FROM id_registry"))
                self.assertEqual(int(reg["vector_types"]),
                                 max(i for i, _, _ in legacy_t) + 1)
                self.assertEqual(report.counts["media_db"]["vectors"], 12)
                self.assertTrue(any("'panoptic_ml'" in w and "registered" in w
                                    for w in report.warnings))

    def test_v6_still_drops(self):
        src = os.path.join(FIXTURES, "v6", "panoptic.db")
        out = os.path.join(self.tmp, "v6")
        ir, report = migrate(src, out)
        media = os.path.join(out, "media.db")
        self.assertEqual(rows(media, "SELECT COUNT(*) FROM vectors"), [(0,)])
        self.assertEqual(rows(media, "SELECT COUNT(*) FROM vector_types"), [(0,)])
        self.assertIsNone(ir.vector_source)
        self.assertEqual(ir.dropped.vectors, 12)
        self.assertTrue(any("dropped by design: 12 vector(s)" in w
                            for w in report.warnings))

    def test_drop_vectors_flag_drops_v7_too(self):
        src = os.path.join(FIXTURES, "v7c", "panoptic.db")
        out = os.path.join(self.tmp, "v7c-drop")
        ir, report = migrate(src, out, keep_vectors=False)
        media = os.path.join(out, "media.db")
        self.assertEqual(rows(media, "SELECT COUNT(*) FROM vectors"), [(0,)])
        self.assertEqual(rows(media, "SELECT COUNT(*) FROM vector_types"), [(0,)])
        self.assertEqual(ir.dropped.vectors, 12)
        self.assertEqual(ir.dropped.vector_types, 1)
        self.assertTrue(any("dropped by design: 12 vector(s)" in w
                            for w in report.warnings))

    def test_cli_flag_default_is_keep(self):
        self.assertFalse(build_parser().parse_args(["a", "b"]).drop_vectors)
        self.assertTrue(build_parser().parse_args(
            ["a", "b", "--drop-vectors"]).drop_vectors)

    def test_vectors_are_streamed_not_loaded(self):
        it = iter_legacy_vectors(os.path.join(FIXTURES, "v7c", "panoptic.db"))
        self.assertTrue(hasattr(it, "__next__"))
        first = next(it)
        self.assertEqual(len(first), 3)
        it.close()


class ValidationTests(_TmpCase):
    """A deliberately damaged COPY of v7c: every bad row is skipped and reported."""

    def setUp(self):
        super().setUp()
        src_dir = os.path.join(self.tmp, "src")
        shutil.copytree(os.path.join(FIXTURES, "v7c"), src_dir)
        self.src = os.path.join(src_dir, "panoptic.db")
        conn = sqlite3.connect(self.src)
        sha1s = [r[0] for r in conn.execute(
            "SELECT sha1 FROM vectors WHERE type_id = 1 ORDER BY sha1")]
        good_len = conn.execute("SELECT LENGTH(data) FROM vectors LIMIT 1").fetchone()[0]
        # a second type with NULL source and NULL params, one good vector
        conn.execute("INSERT INTO vector_type (id, source, params) "
                     "VALUES (5, NULL, NULL)")
        conn.execute("INSERT INTO vectors VALUES (5, ?, ?)",
                     (sha1s[0], b"\0" * 8))
        # damage four type-1 rows in four different ways
        conn.execute("UPDATE vectors SET data = ? WHERE type_id = 1 AND sha1 = ?",
                     (b"\1" * (good_len - 2), sha1s[1]))         # not %4
        conn.execute("UPDATE vectors SET data = ? WHERE type_id = 1 AND sha1 = ?",
                     (b"\1" * (good_len + 4), sha1s[2]))         # wrong length
        conn.execute("UPDATE vectors SET data = NULL WHERE type_id = 1 AND sha1 = ?",
                     (sha1s[3],))                                 # NULL
        conn.execute("INSERT INTO vectors VALUES (1, 'deadbeef', ?)",
                     (b"\0" * good_len,))                         # no instance
        conn.execute("INSERT INTO vectors VALUES (99, ?, ?)",
                     (sha1s[0], b"\0" * good_len))                # unknown type
        conn.commit()
        conn.close()
        self.good_len = good_len

    def test_bad_rows_are_skipped_reported_and_postconditions_hold(self):
        out = os.path.join(self.tmp, "out")
        ir, report = migrate(self.src, out)
        media = os.path.join(out, "media.db")
        # 12 legacy + 1 (type 5) + 1 (orphan sha1) + 1 (type 99) = 15 source rows;
        # 5 bad -> 10 written
        self.assertEqual(ir.vector_source.rows, 15)
        self.assertEqual(rows(media, "SELECT COUNT(*) FROM vectors"), [(10,)])
        self.assertEqual(rows(media, "SELECT id, source, params FROM vector_types "
                                     "ORDER BY id"),
                         [(1, "panoptic_ml", '{"model": "clip-fixture", "dim": 16}'),
                          (5, "unknown", "{}")])
        self.assertEqual(rows(media, "SELECT DISTINCT LENGTH(data) FROM vectors "
                                     "WHERE type_id = 1"), [(self.good_len,)])
        joined = "\n".join(report.warnings)
        for reason in ("not a multiple of 4", "differs from its type's",
                       "NULL, empty or not a BLOB", "no migrated instance",
                       "not a vector_type"):
            self.assertIn(reason, joined)
        self.assertIn("vector_type 5 has no source", joined)
        self.assertIn("has no 'model' param", joined)
        self.assertEqual(
            int(dict(rows(os.path.join(out, "project.db"),
                          "SELECT key, value FROM id_registry"))["vector_types"]), 6)

    def test_the_source_copy_is_untouched_by_the_run(self):
        def read():
            with open(self.src, "rb") as fh:
                return fh.read()
        before = read()
        migrate(self.src, os.path.join(self.tmp, "out2"))
        self.assertEqual(read(), before)


class VectorPostConditionTrapTests(_TmpCase):
    def setUp(self):
        super().setUp()
        src = os.path.join(FIXTURES, "v7c", "panoptic.db")
        self.out = os.path.join(self.tmp, "v7c")
        migrate(src, self.out)
        self.paths = tuple(os.path.join(self.out, n)
                           for n in ("project.db", "data.db", "media.db"))

    def _failures(self, expected=None):
        return PostConditions(*self.paths, expected=expected).run()

    def test_clean_output_passes(self):
        self.assertEqual(self._failures({"vectors": 12, "vector_types": 1}), [])

    def test_a_lost_vector_is_caught(self):
        conn = sqlite3.connect(self.paths[2])
        conn.execute("DELETE FROM vectors WHERE rowid IN "
                     "(SELECT rowid FROM vectors LIMIT 1)")
        conn.commit()
        conn.close()
        f = self._failures({"vectors": 12, "vector_types": 1})
        self.assertTrue(any(x.startswith("vectors count") for x in f), f)

    def test_a_truncated_vector_is_caught(self):
        conn = sqlite3.connect(self.paths[2])
        conn.execute("UPDATE vectors SET data = substr(data, 1, 6) WHERE rowid IN "
                     "(SELECT rowid FROM vectors LIMIT 1)")
        conn.commit()
        conn.close()
        f = self._failures()
        self.assertTrue(any(x.startswith("vectors.data") for x in f), f)

    def test_an_orphan_vector_type_ref_is_caught(self):
        conn = sqlite3.connect(self.paths[2])
        conn.execute("UPDATE vectors SET type_id = 77 WHERE rowid IN "
                     "(SELECT rowid FROM vectors LIMIT 1)")
        conn.commit()
        conn.close()
        f = self._failures()
        self.assertTrue(any(x.startswith("vectors.type_id") for x in f), f)


if __name__ == "__main__":
    unittest.main()
