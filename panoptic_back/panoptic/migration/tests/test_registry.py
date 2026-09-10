"""Task 3.4 -- the panoptic *home* registry.

The one invariant everything here exists to hold:

    panoptic.db `projects.id`  ==  project.db `project_config.id`

`Panoptic.load_project` re-reads the folder and raises `ID mismatch` when they
differ, so these tests assert that no code path can register an id that is not
read back out of a real `project.db`.

Run:  python3 -m unittest migrator.tests.test_registry
      python3 migrator/tests/test_registry.py --table
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

from panoptic.migration import cli, home
from panoptic.migration.errors import AlreadyMigrated, UnknownShape
from panoptic.migration.writers.panoptic_db import (DEFAULT_USER_ID, HomeDbError,
                                          PanopticHomeWriter,
                                          read_project_config)

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

LEGACY_HOME_SQL = """
CREATE TABLE panoptic (key TEXT PRIMARY KEY, value TEXT NOT NULL);
INSERT INTO panoptic (key, value) VALUES ('db_version', '1');
CREATE TABLE projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, path TEXT NOT NULL,
    description TEXT, ignored_plugins JSON);
CREATE TABLE plugins (
    name TEXT PRIMARY KEY, path TEXT NOT NULL, type TEXT NOT NULL, source TEXT);
"""


def make_legacy_home(path, projects=(), plugins=()):
    conn = sqlite3.connect(path)
    conn.executescript(LEGACY_HOME_SQL)
    for i, (name, folder, desc, ignored) in enumerate(projects, 1):
        conn.execute("INSERT INTO projects (id, name, path, description, "
                     "ignored_plugins) VALUES (?,?,?,?,?)",
                     (i, name, folder, desc, json.dumps(ignored)))
    for row in plugins:
        conn.execute("INSERT INTO plugins (name, path, type, source) "
                     "VALUES (?,?,?,?)", row)
    conn.commit()
    conn.close()
    return path


def migrate_fixture(shape, target):
    """Run the real project migration on a fixture -> a real project.db."""
    os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
    rc = cli.main([os.path.join(FIXTURES, shape), target, "-q"])
    assert rc == 0, "migrating %s failed with rc=%d" % (shape, rc)
    return target


class TempCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="migrator-3.4-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def p(self, *parts):
        return os.path.join(self.tmp, *parts)


# ---------------------------------------------------------------------------
# reading the legacy home
# ---------------------------------------------------------------------------

class TestLegacyHomeReader(TempCase):
    def test_reads_the_db_shape(self):
        src = make_legacy_home(
            self.p("legacy.db"),
            projects=[("alpha", "/a", "first", []),
                      ("beta", "/b", None, ["PanopticML"])],
            plugins=[("PanopticML", "/plugins/ml", "pip", "panopticml")])
        h = home.read_legacy_home(src)
        self.assertEqual(h.shape, "legacy-db")
        self.assertEqual(h.version, 1)
        self.assertEqual([p.name for p in h.projects], ["alpha", "beta"])
        self.assertEqual(h.projects[1].ignored_plugins, ["PanopticML"])
        self.assertEqual(h.plugins[0].source, "panopticml")
        self.assertEqual(h.warnings, [])

    def test_null_ignored_plugins_reads_as_empty_list(self):
        src = make_legacy_home(self.p("legacy.db"))
        conn = sqlite3.connect(src)
        conn.execute("INSERT INTO projects (id, name, path) VALUES (1,'x','/x')")
        conn.commit()
        conn.close()
        h = home.read_legacy_home(src)
        self.assertEqual(h.projects[0].ignored_plugins, [])

    def test_unexpected_db_version_warns_but_still_reads(self):
        src = make_legacy_home(self.p("legacy.db"))
        conn = sqlite3.connect(src)
        conn.execute("UPDATE panoptic SET value='2' WHERE key='db_version'")
        conn.commit()
        conn.close()
        h = home.read_legacy_home(src)
        self.assertEqual(h.version, 2)
        self.assertTrue(any("db_version" in w for w in h.warnings))

    def test_reads_the_json_shape(self):
        """<= 0.6.x kept the registry in projects.json, not a DB at all."""
        src = self.p("projects.json")
        with open(src, "w") as fh:
            json.dump({"version": 1,
                       "projects": [{"name": "alpha", "path": "/a"},
                                    {"name": "beta", "path": "/b"}],
                       "plugins": [{"name": "ML", "path": "/p/ml",
                                    "type": "pip", "source": "panopticml"}]}, fh)
        h = home.read_legacy_home(src)
        self.assertEqual(h.shape, "legacy-json")
        # projects.json had no ids; 0.7 assigned i+1 on import, and so do we
        self.assertEqual([p.id for p in h.projects], [1, 2])
        self.assertEqual(h.plugins[0].type, "pip")

    def test_pre_version_json_derives_the_plugin_type_from_source_url(self):
        src = self.p("projects.json")
        with open(src, "w") as fh:
            json.dump({"projects": [],
                       "plugins": [{"name": "g", "path": "/p/g",
                                    "source_url": "https://x/y.git"},
                                   {"name": "l", "path": "/p/l",
                                    "source_url": None}]}, fh)
        h = home.read_legacy_home(src)
        self.assertEqual([(p.name, p.type) for p in h.plugins],
                         [("g", "git"), ("l", "local")])
        self.assertTrue(any("version" in w for w in h.warnings))

    def test_detect_refuses_a_foreign_database(self):
        path = self.p("other.db")
        sqlite3.connect(path).executescript("CREATE TABLE nope (x);")
        with self.assertRaises(UnknownShape):
            home.detect_home(path)

    def test_reading_an_already_migrated_home_is_refused(self):
        with PanopticHomeWriter(self.p("new.db")):
            pass
        self.assertEqual(home.detect_home(self.p("new.db")), "target-db")
        with self.assertRaises(AlreadyMigrated):
            home.read_legacy_home(self.p("new.db"))

    def test_source_is_never_written(self):
        src = make_legacy_home(self.p("legacy.db"),
                               projects=[("a", "/a", None, [])])
        before = (os.path.getmtime(src), os.path.getsize(src))
        home.read_legacy_home(src)
        home.migrate_home(src, self.p("new.db"))
        self.assertEqual((os.path.getmtime(src), os.path.getsize(src)), before)


# ---------------------------------------------------------------------------
# plugin type mapping -- the one field that is not a copy
# ---------------------------------------------------------------------------

class TestPluginTypeMap(unittest.TestCase):
    def test_local_is_renamed_path(self):
        mapped, warning = home.map_plugin_type("local")
        self.assertEqual(mapped, "path")
        self.assertIsNotNone(warning)

    def test_git_and_pip_pass_through_silently(self):
        for value in ("git", "pip"):
            mapped, warning = home.map_plugin_type(value)
            self.assertEqual(mapped, value)
            self.assertIsNone(warning)

    def test_unknown_type_falls_back_to_path_with_a_warning(self):
        mapped, warning = home.map_plugin_type("wat")
        self.assertEqual(mapped, "path")
        self.assertIn("wat", warning)


# ---------------------------------------------------------------------------
# the writer
# ---------------------------------------------------------------------------

class TestHomeWriter(TempCase):
    def test_a_new_home_has_config_and_the_default_user(self):
        path = self.p("panoptic.db")
        with PanopticHomeWriter(path) as w:
            self.assertTrue(w.created)
            instance_id = w.instance_id
        conn = sqlite3.connect(path)
        config = dict(conn.execute("SELECT key, value FROM panoptic_config"))
        self.assertEqual(set(config), {"id", "name", "description"})
        self.assertEqual(json.loads(config["id"]), instance_id)
        self.assertIsNone(config["name"])
        self.assertEqual(
            conn.execute("SELECT id, name, description, password_hash "
                         "FROM users").fetchall(),
            [(DEFAULT_USER_ID, "default", "default user", None)])
        self.assertEqual(conn.execute("SELECT value FROM _version WHERE "
                                      "key='db_version'").fetchone()[0], 1)
        conn.close()

    def test_reopening_keeps_the_instance_id_and_the_user(self):
        path = self.p("panoptic.db")
        with PanopticHomeWriter(path) as w:
            first = w.instance_id
        with PanopticHomeWriter(path) as w:
            self.assertFalse(w.created)
            self.assertEqual(w.instance_id, first)
        conn = sqlite3.connect(path)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0], 1)
        conn.close()

    def test_registering_twice_is_one_row(self):
        path = self.p("panoptic.db")
        with PanopticHomeWriter(path) as w:
            self.assertEqual(w.register_project("uuid-1", self.p("proj")),
                             "registered")
            self.assertEqual(w.register_project("uuid-1", self.p("proj")),
                             "updated")
            self.assertEqual(len(w.projects()), 1)

    def test_a_path_registered_under_a_stale_id_is_replaced(self):
        path = self.p("panoptic.db")
        with PanopticHomeWriter(path) as w:
            w.register_project("old-uuid", self.p("proj"))
            w.register_project("new-uuid", self.p("proj"))
            rows = w.projects()
            self.assertEqual([r[0] for r in rows], ["new-uuid"])
            self.assertTrue(any("replaced" in n for n in w.notes))

    def test_excluded_plugins_is_json_and_never_null(self):
        path = self.p("panoptic.db")
        with PanopticHomeWriter(path) as w:
            w.register_project("uuid-1", self.p("a"))
            w.register_project("uuid-2", self.p("b"), excluded_plugins=["ML"])
        conn = sqlite3.connect(path)
        rows = dict(conn.execute("SELECT id, excluded_plugins FROM projects"))
        conn.close()
        self.assertEqual(json.loads(rows["uuid-1"]), [])
        self.assertEqual(json.loads(rows["uuid-2"]), ["ML"])

    def test_a_plugin_without_a_source_reuses_its_install_path(self):
        path = self.p("panoptic.db")
        with PanopticHomeWriter(path) as w:
            w.register_plugin("Local", "/plugins/local", "local", None)
            row = w.plugins()[0]
        # source_path is NOT NULL upstream, and 'path' plugins reinstall from it
        self.assertEqual(row, ("Local", "/plugins/local", "path", "/plugins/local"))

    def test_a_legacy_home_is_refused_as_a_target(self):
        src = make_legacy_home(self.p("legacy.db"))
        with self.assertRaises(HomeDbError) as ctx:
            PanopticHomeWriter(src).open()
        self.assertIn("migrate-home", str(ctx.exception))

    def test_a_foreign_file_is_refused_as_a_target(self):
        path = self.p("other.db")
        sqlite3.connect(path).executescript("CREATE TABLE nope (x);")
        with self.assertRaises(HomeDbError):
            PanopticHomeWriter(path).open()

    def test_no_wal_sidecars_are_left_behind(self):
        path = self.p("panoptic.db")
        with PanopticHomeWriter(path) as w:
            w.register_project("uuid-1", self.p("proj"))
        self.assertFalse(os.path.exists(path + "-wal"))
        self.assertFalse(os.path.exists(path + "-shm"))


# ---------------------------------------------------------------------------
# the invariant, against a really migrated fixture
# ---------------------------------------------------------------------------

class TestRegistrationInvariant(TempCase):
    def test_the_pipeline_registers_the_id_project_db_holds(self):
        target = self.p("v7c")
        home_db = self.p("panoptic.db")
        rc = cli.main([os.path.join(FIXTURES, "v7c"), target, "-q",
                       "--panoptic-db", home_db])
        self.assertEqual(rc, 0)
        expected, _, _ = read_project_config(target)
        conn = sqlite3.connect(home_db)
        rows = conn.execute("SELECT id, path, name FROM projects").fetchall()
        conn.close()
        self.assertEqual(rows, [(expected, os.path.abspath(target), "v7c")])

    def test_without_the_flag_no_home_db_is_touched(self):
        target = self.p("v7c")
        rc = cli.main([os.path.join(FIXTURES, "v7c"), target, "-q"])
        self.assertEqual(rc, 0)
        self.assertEqual(os.listdir(self.tmp), ["v7c"])

    def test_register_subcommand_matches_the_pipeline(self):
        target = migrate_fixture("v5", self.p("v5"))
        home_db = self.p("panoptic.db")
        self.assertEqual(cli.main(["register", target, "--panoptic-db",
                                   home_db, "-q"]), 0)
        expected, _, _ = read_project_config(target)
        conn = sqlite3.connect(home_db)
        self.assertEqual(conn.execute("SELECT id FROM projects").fetchone()[0],
                         expected)
        conn.close()

    def test_register_refuses_a_folder_without_a_project_db(self):
        os.makedirs(self.p("empty"))
        self.assertEqual(cli.main(["register", self.p("empty"),
                                   "--panoptic-db", self.p("p.db"), "-q"]), 1)

    def test_migrate_home_resolves_projects_through_map(self):
        migrated = migrate_fixture("v7c", self.p("migrated"))
        src = make_legacy_home(
            self.p("legacy.db"),
            projects=[("theproject", "/old/place", "a description", ["ML"]),
                      ("gone", "/nowhere", None, [])],
            plugins=[("ML", "/plugins/ml", "pip", "panopticml")])
        result = home.migrate_home(src, self.p("panoptic.db"),
                                   {"/old/place": migrated})
        expected, _, _ = read_project_config(migrated)
        self.assertEqual([r[1] for r in result.registered], [expected])
        self.assertEqual([s[0] for s in result.skipped], [2])
        self.assertEqual(result.plugins, ["ML"])
        conn = sqlite3.connect(self.p("panoptic.db"))
        row = conn.execute("SELECT id, name, excluded_plugins FROM "
                           "projects").fetchone()
        conn.close()
        self.assertEqual(row, (expected, "theproject", '["ML"]'))
        self.assertTrue(any("description" in n for n in result.notes))

    def test_migrate_home_never_invents_an_id(self):
        """An unmigrated project is skipped, not given a fresh UUID.

        A UUID no `project.db` holds is exactly what `load_project` refuses.
        """
        src = make_legacy_home(self.p("legacy.db"),
                               projects=[("a", "/nowhere", None, [])])
        result = home.migrate_home(src, self.p("panoptic.db"))
        self.assertEqual(result.registered, [])
        self.assertEqual(len(result.skipped), 1)
        conn = sqlite3.connect(self.p("panoptic.db"))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM projects")
                         .fetchone()[0], 0)
        conn.close()

    def test_migrate_home_is_rerunnable(self):
        migrated = migrate_fixture("v7c", self.p("migrated"))
        src = make_legacy_home(self.p("legacy.db"),
                               projects=[("p", "/old", None, [])],
                               plugins=[("ML", "/p/ml", "pip", "panopticml")])
        out = self.p("panoptic.db")
        first = home.migrate_home(src, out, {"/old": migrated})
        second = home.migrate_home(src, out, {"/old": migrated})
        self.assertEqual(first.instance_id, second.instance_id)
        conn = sqlite3.connect(out)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM projects")
                         .fetchone()[0], 1)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM plugins")
                         .fetchone()[0], 1)
        conn.close()


class TestAllFixturesRegister(TempCase):
    """Every fixture migrates and registers with a matching id."""

    def test_all_eleven(self):
        home_db = self.p("panoptic.db")
        shapes = sorted(d for d in os.listdir(FIXTURES)
                        if os.path.isfile(os.path.join(FIXTURES, d,
                                                       "panoptic.db")))
        self.assertEqual(len(shapes), 11)
        for shape in shapes:
            target = migrate_fixture(shape, self.p("out", shape))
            self.assertEqual(cli.main(["register", target, "--panoptic-db",
                                       home_db, "-q"]), 0)
        conn = sqlite3.connect(home_db)
        rows = conn.execute("SELECT id, path, name FROM projects").fetchall()
        conn.close()
        self.assertEqual(len(rows), 11)
        self.assertEqual(len({r[0] for r in rows}), 11)
        for project_id, path, _ in rows:
            self.assertEqual(read_project_config(path)[0], project_id)


def print_table():
    import tempfile as _tf
    tmp = _tf.mkdtemp(prefix="migrator-3.4-table-")
    home_db = os.path.join(tmp, "panoptic.db")
    shapes = sorted(d for d in os.listdir(FIXTURES)
                    if os.path.isfile(os.path.join(FIXTURES, d, "panoptic.db")))
    print("%-6s %-38s %-8s %s" % ("shape", "projects.id (== project_config.id)",
                                  "action", "match"))
    print("-" * 72)
    for shape in shapes:
        target = migrate_fixture(shape, os.path.join(tmp, "out", shape))
        cli.main(["register", target, "--panoptic-db", home_db, "-q"])
        pid, _, _ = read_project_config(target)
        conn = sqlite3.connect(home_db)
        row = conn.execute("SELECT id FROM projects WHERE path=?",
                           (os.path.abspath(target),)).fetchone()
        conn.close()
        print("%-6s %-38s %-8s %s" % (shape, pid, "registered",
                                      "OK" if row and row[0] == pid else "FAIL"))
    conn = sqlite3.connect(home_db)
    print("\nusers          : %s" % conn.execute("SELECT id FROM users").fetchall())
    print("panoptic_config: %s" % conn.execute(
        "SELECT key, value FROM panoptic_config").fetchall())
    conn.close()
    shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# task 5.1 -- discovery must report EVERY registry, never silently pick one
# ---------------------------------------------------------------------------

class TestHomeDiscovery(TempCase):
    """Two registries side by side is the normal case, not the exotic one.

    `panoptic` and `panoptic-dev` are separate console scripts writing
    `panoptic.db` and `panoptic-dev.db` in the same folder with *different*
    project lists (task 4.3 found exactly that on the development machine).
    Probing only the default name loses half the user's projects.
    """

    def test_every_db_in_the_folder_is_found(self):
        make_legacy_home(self.p("panoptic.db"),
                         projects=[("a", "/a", None, [])])
        make_legacy_home(self.p("panoptic-dev.db"),
                         projects=[("b", "/b", None, []), ("c", "/c", None, [])])
        found = home.discover_homes(self.tmp)
        self.assertEqual([os.path.basename(d.path) for d in found],
                         ["panoptic.db", "panoptic-dev.db"])
        self.assertEqual([d.projects for d in found], [1, 2])
        self.assertEqual([d.problem for d in found], [None, None])

    def test_the_0_6_8_projects_json_is_found_alongside_the_dbs(self):
        make_legacy_home(self.p("panoptic.db"))
        with open(self.p("projects.json"), "w") as fh:
            json.dump({"projects": [{"name": "j", "path": "/j"}],
                       "plugins": []}, fh)
        found = home.discover_homes(self.tmp)
        self.assertEqual([d.shape for d in found], ["legacy-db", "legacy-json"])
        self.assertEqual(found[1].projects, 1)

    def test_an_unreadable_registry_is_reported_not_dropped(self):
        make_legacy_home(self.p("panoptic.db"))
        with open(self.p("broken.db"), "wb") as fh:
            fh.write(b"not a database at all")
        found = home.discover_homes(self.tmp)
        self.assertEqual(len(found), 2)
        broken = [d for d in found if d.path.endswith("broken.db")][0]
        self.assertIsNotNone(broken.problem)
        self.assertEqual([d.path for d in home.usable_homes(found)],
                         [os.path.join(self.tmp, "panoptic.db")])

    def test_an_already_migrated_home_is_listed_as_such(self):
        with PanopticHomeWriter(self.p("panoptic.db")):
            pass
        found = home.discover_homes(self.tmp)
        self.assertEqual(found[0].shape, "target-db")
        self.assertIn("already in the new format", found[0].problem)
        self.assertEqual(home.usable_homes(found), [])

    def test_no_registry_at_all_is_an_empty_list_not_a_crash(self):
        self.assertEqual(home.discover_homes(self.tmp), [])
        self.assertEqual(home.discover_homes(self.p("does-not-exist")), [])


class TestMigrateHomeRefusesToChoose(TempCase):
    """`migrate-home` with no source and several registries must not pick one."""

    def _args(self, all_homes=False):
        class A:
            source = None
        A.all_homes = all_homes
        return A

    def setUp(self):
        super().setUp()
        self._real = home.discover_homes
        self._lines = []

    def tearDown(self):
        home.discover_homes = self._real
        cli.discover_homes = self._real
        super().tearDown()

    def _patch(self, base):
        cli.discover_homes = lambda b=None: self._real(base)

    def test_two_registries_are_both_listed_and_the_run_stops(self):
        make_legacy_home(self.p("panoptic.db"), projects=[("a", "/a", None, [])])
        make_legacy_home(self.p("panoptic-dev.db"),
                         projects=[("b", "/b", None, [])])
        self._patch(self.tmp)
        sources, rc = cli.resolve_home_sources(self._args(), self._lines.append)
        self.assertIsNone(sources)
        self.assertEqual(rc, cli.EXIT_USAGE)
        printed = "\n".join(str(x) for x in self._lines)
        self.assertIn("panoptic.db", printed)
        self.assertIn("panoptic-dev.db", printed)

    def test_all_takes_every_one_of_them(self):
        make_legacy_home(self.p("panoptic.db"), projects=[("a", "/a", None, [])])
        make_legacy_home(self.p("panoptic-dev.db"),
                         projects=[("b", "/b", None, [])])
        self._patch(self.tmp)
        sources, rc = cli.resolve_home_sources(self._args(all_homes=True),
                                               self._lines.append)
        self.assertIsNone(rc)
        self.assertEqual([os.path.basename(s) for s in sources],
                         ["panoptic.db", "panoptic-dev.db"])

    def test_a_single_registry_needs_no_flag(self):
        make_legacy_home(self.p("panoptic.db"), projects=[("a", "/a", None, [])])
        self._patch(self.tmp)
        sources, rc = cli.resolve_home_sources(self._args(), self._lines.append)
        self.assertIsNone(rc)
        self.assertEqual(len(sources), 1)


class TestRunReport(TempCase):
    """Every run leaves a report behind -- task 5.1's deliverable."""

    def _run(self, argv, reports):
        """Run the CLI with the report dir pointed at `reports`, and restore it.

        Restoring matters: the suite-wide default set in `tests/__init__` is
        what keeps every *other* test from dropping files in the repo.
        """
        old = os.environ.get("MIGRATOR_REPORT_DIR")
        os.environ["MIGRATOR_REPORT_DIR"] = reports
        try:
            return cli.main(argv)
        finally:
            if old is None:
                os.environ.pop("MIGRATOR_REPORT_DIR", None)
            else:
                os.environ["MIGRATOR_REPORT_DIR"] = old

    def test_a_migration_writes_a_markdown_and_a_json_report(self):
        reports = self.p("reports")
        rc = self._run([os.path.join(FIXTURES, "v7c"), self.p("out"), "-q"],
                       reports)
        self.assertEqual(rc, 0)
        names = sorted(os.listdir(reports))
        self.assertEqual(len(names), 2, names)
        md = [n for n in names if n.endswith(".md")][0]
        with open(os.path.join(reports, md), encoding="utf-8") as fh:
            text = fh.read()
        # the four things a hand-run report has to answer
        self.assertIn("| status | **ok** |", text)
        self.assertIn("read-legacy", text)          # what ran
        self.assertIn("## Warnings", text)          # what was dropped
        self.assertIn("1.2 KB per instance", text)  # the known scale limit

    def test_no_report_writes_nothing(self):
        reports = self.p("reports2")
        rc = self._run([os.path.join(FIXTURES, "v7c"), self.p("out2"),
                        "-q", "--no-report"], reports)
        self.assertEqual(rc, 0)
        self.assertFalse(os.path.exists(reports))


if __name__ == "__main__":
    if "--table" in sys.argv:
        print_table()
    else:
        unittest.main()
