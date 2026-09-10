"""Legacy (0.x) project discovery + migration service.

Everything here runs against throwaway temp dirs; no test ever reads or writes
the user's real ~/.panoptic or ~/Library/Application Support/panoptic.
"""
import os
import shutil
import sqlite3
from pathlib import Path

import pytest

from panoptic.core.databases.panoptic.models import LegacyMigration
from panoptic.core.databases.panoptic.panoptic_db import PanopticDB
from panoptic.core.panoptic.panoptic import Panoptic

FIXTURES = Path(__file__).parent.parent / 'panoptic' / 'migration' / 'tests' / 'fixtures'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_legacy_home_db(path: Path, projects: list[tuple[int, str, str]],
                         plugins: list[str] = ()):
    """A 0.7-shape legacy registry: `panoptic`, `projects`, `plugins`."""
    conn = sqlite3.connect(str(path))
    conn.executescript("""
        CREATE TABLE panoptic (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE projects (id INTEGER PRIMARY KEY, name TEXT, path TEXT,
                               description TEXT, ignored_plugins TEXT);
        CREATE TABLE plugins (name TEXT PRIMARY KEY, path TEXT, type TEXT, source TEXT);
    """)
    conn.execute("INSERT INTO panoptic VALUES ('db_version', '1')")
    for id_, name, p in projects:
        conn.execute("INSERT INTO projects VALUES (?,?,?,?,?)", (id_, name, p, '', '[]'))
    for name in plugins:
        conn.execute("INSERT INTO plugins VALUES (?,?,?,?)", (name, f'/p/{name}', 'pip', name))
    conn.commit()
    conn.close()


def _copy_fixture(shape: str, dest: Path) -> Path:
    """A copy of a vendored legacy project fixture (never the original)."""
    src = FIXTURES / shape
    shutil.copytree(src, dest)
    return dest


@pytest.fixture
def panoptic(tmp_path, monkeypatch):
    monkeypatch.delenv('PANOPTIC_NO_LEGACY_SCAN', raising=False)
    p = Panoptic(tmp_path / 'home' / 'panoptic.db')
    p.start()
    yield p
    p.close()


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def test_panoptic_db_v1_upgrades_to_v2(tmp_path):
    """A panoptic.db written by the previous release gains legacy_migrations."""
    db_path = tmp_path / 'panoptic.db'
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE _version (key TEXT PRIMARY KEY NOT NULL, value INTEGER NOT NULL);
        INSERT INTO _version VALUES ('db_version', 1);
        CREATE TABLE panoptic_config (key TEXT PRIMARY KEY, value JSON);
        CREATE TABLE users (id TEXT PRIMARY KEY, name TEXT, description TEXT, password_hash TEXT);
        CREATE TABLE projects (id TEXT PRIMARY KEY, path TEXT, name TEXT, excluded_plugins JSON);
        CREATE TABLE plugins (id TEXT PRIMARY KEY, install_path TEXT, source_type TEXT, source_path TEXT);
    """)
    conn.execute("INSERT INTO projects VALUES ('pid', '/some/path', 'old', '[]')")
    conn.commit()
    conn.close()

    db = PanopticDB(str(db_path))
    try:
        assert db._get_db_version() == 2
        assert db._table_exists('legacy_migrations')
        # pre-existing rows survive the upgrade
        assert [p.id for p in db.get_projects()] == ['pid']
        db.set_legacy_migration(LegacyMigration(legacy_path='/old', status='done'))
        assert db.get_legacy_migration('/old').status == 'done'
        # the config key exists with its default
        assert db.config.legacy_scan_dismissed is False
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def test_discover_three_registries_one_broken(panoptic, tmp_path):
    datadir = tmp_path / 'legacy_home'
    datadir.mkdir()
    proj = tmp_path / 'old_project'
    _copy_fixture('v7c', proj)

    _make_legacy_home_db(datadir / 'panoptic.db', [(1, 'Alpha', str(proj))],
                         plugins=['panopticml'])
    (datadir / 'projects.json').write_text(
        '{"version": 1, "projects": [{"name": "Beta", "path": "/nope/gone"}], "plugins": []}')
    (datadir / 'panoptic-dev.db').write_bytes(b'this is not a sqlite database at all')

    scan = panoptic.legacy.discover(base=datadir)

    assert len(scan.registries) == 3, [r.path for r in scan.registries]
    broken = [r for r in scan.registries if r.problem]
    assert len(broken) == 1
    assert broken[0].path.endswith('panoptic-dev.db')

    by_name = {p.name: p for p in scan.projects}
    assert set(by_name) == {'Alpha', 'Beta'}

    alpha = by_name['Alpha']
    assert alpha.exists and alpha.problem is None
    assert alpha.shape == 'v7c'
    assert alpha.instance_count is not None and alpha.instance_count > 0
    assert alpha.plugins == ['panopticml']
    assert alpha.suggested_path == str(tmp_path / 'Alpha-v2')

    beta = by_name['Beta']
    assert beta.exists is False
    assert beta.problem


def test_missing_project_message_is_not_about_permissions(panoptic, tmp_path):
    datadir = tmp_path / 'legacy_home'
    datadir.mkdir()
    _make_legacy_home_db(datadir / 'panoptic.db',
                         [(1, 'Gone', '/Volumes/NotMounted/proj')])
    scan = panoptic.legacy.discover(base=datadir)
    problem = scan.projects[0].problem
    assert 'not mounted' in problem or 'not reachable' in problem


def test_discover_skipped_by_env(panoptic, tmp_path, monkeypatch):
    monkeypatch.setenv('PANOPTIC_NO_LEGACY_SCAN', '1')
    scan = panoptic.legacy.discover(base=tmp_path)
    assert scan.skipped and scan.reason == 'PANOPTIC_NO_LEGACY_SCAN=1'
    assert scan.projects == []


def test_dismiss_all_sets_config_flag(panoptic, tmp_path):
    datadir = tmp_path / 'legacy_home'
    datadir.mkdir()
    _make_legacy_home_db(datadir / 'panoptic.db', [(1, 'Alpha', str(tmp_path / 'x'))])
    panoptic.legacy.dismiss()
    assert panoptic.db.config.legacy_scan_dismissed is True
    assert panoptic.legacy.discover(base=datadir).skipped is True


def test_dismiss_one_path_hides_it(panoptic, tmp_path):
    datadir = tmp_path / 'legacy_home'
    datadir.mkdir()
    proj = tmp_path / 'old_project'
    _copy_fixture('v7c', proj)
    _make_legacy_home_db(datadir / 'panoptic.db', [(1, 'Alpha', str(proj))])

    assert len(panoptic.legacy.discover(base=datadir).projects) == 1
    panoptic.legacy.dismiss(str(proj))
    assert panoptic.legacy.discover(base=datadir).projects == []


def test_idempotence_done_row_is_not_reoffered(panoptic, tmp_path):
    datadir = tmp_path / 'legacy_home'
    datadir.mkdir()
    proj = tmp_path / 'old_project'
    _copy_fixture('v7c', proj)
    _make_legacy_home_db(datadir / 'panoptic.db', [(1, 'Alpha', str(proj))])

    assert len(panoptic.legacy.discover(base=datadir).projects) == 1
    panoptic.db.set_legacy_migration(LegacyMigration(
        legacy_path=str(proj), new_path=str(tmp_path / 'new'), status='done'))
    assert panoptic.legacy.discover(base=datadir).projects == []


def test_failed_row_is_still_offered(panoptic, tmp_path):
    """A failed migration must remain retryable."""
    datadir = tmp_path / 'legacy_home'
    datadir.mkdir()
    proj = tmp_path / 'old_project'
    _copy_fixture('v7c', proj)
    _make_legacy_home_db(datadir / 'panoptic.db', [(1, 'Alpha', str(proj))])
    panoptic.db.set_legacy_migration(LegacyMigration(
        legacy_path=str(proj), new_path=str(tmp_path / 'new'), status='failed'))

    projects = panoptic.legacy.discover(base=datadir).projects
    assert len(projects) == 1
    assert projects[0].status == 'failed'


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------

def test_refuse_non_empty_destination(panoptic, tmp_path):
    proj = _copy_fixture('v7c', tmp_path / 'src')
    dest = tmp_path / 'dest'
    dest.mkdir()
    (dest / 'something.txt').write_text('hi')
    with pytest.raises(ValueError, match='not empty'):
        panoptic.legacy.migrate(str(proj), str(dest))


def test_empty_destination_is_accepted(panoptic, tmp_path):
    proj = _copy_fixture('v7c', tmp_path / 'src')
    dest = tmp_path / 'dest'
    dest.mkdir()
    assert panoptic.legacy.check_destination(str(proj), str(dest)) is not None


def test_refuse_missing_source(panoptic, tmp_path):
    with pytest.raises(ValueError, match='does not exist'):
        panoptic.legacy.migrate(str(tmp_path / 'nope'), str(tmp_path / 'dest'))


def test_refuse_source_without_panoptic_db(panoptic, tmp_path):
    src = tmp_path / 'notaproject'
    src.mkdir()
    with pytest.raises(ValueError, match='no panoptic.db'):
        panoptic.legacy.migrate(str(src), str(tmp_path / 'dest'))


def test_refuse_destination_inside_source(panoptic, tmp_path):
    proj = _copy_fixture('v7c', tmp_path / 'src')
    with pytest.raises(ValueError, match='inside the source'):
        panoptic.legacy.migrate(str(proj), str(proj / 'v2'))


def test_refuse_destination_equal_to_source(panoptic, tmp_path):
    proj = _copy_fixture('v7c', tmp_path / 'src')
    with pytest.raises(ValueError, match='different folder'):
        panoptic.legacy.migrate(str(proj), str(proj))


# ---------------------------------------------------------------------------
# End to end
# ---------------------------------------------------------------------------

def test_migrate_fixture_end_to_end(panoptic, tmp_path):
    """migrate v7c → import_project → load_project reads real content."""
    datadir = tmp_path / 'legacy_home'
    datadir.mkdir()
    proj = _copy_fixture('v7c', tmp_path / 'old_project')
    _make_legacy_home_db(datadir / 'panoptic.db', [(1, 'Alpha', str(proj))],
                         plugins=['panopticml'])
    panoptic.legacy.discover(base=datadir)

    # the run object is mutated in place, so snapshot what we care about
    states = []
    panoptic.legacy.on_migration_state = lambda r: states.append((r.status, r.stage))

    dest = tmp_path / 'migrated'
    run = panoptic.legacy.migrate(str(proj), str(dest), name='Alpha')
    panoptic.legacy._thread.join(timeout=300)

    assert run.status == 'done', run.error
    assert run.project_id
    assert run.plugins == ['panopticml']
    assert (dest / 'project.db').is_file()
    assert Path(run.report_path).is_file()
    assert Path(run.report_path).with_suffix('.json').is_file()

    # every pipeline stage was reported
    stages = [stage for _, stage in states]
    assert 'read-legacy' in stages and 'check' in stages
    assert states[-1][0] == 'done'

    # registered, and the source is untouched
    assert any(k.path == str(dest) for k in panoptic.get_projects())
    assert (proj / 'panoptic.db').is_file()

    # not offered again
    assert panoptic.legacy.discover(base=datadir).projects == []

    # and it actually opens
    project = panoptic.load_project(run.project_id)
    try:
        from panoptic.core.databases.data.data_reader import DataReader
        with DataReader(str(project.data_db_path)) as r:
            assert len(r.get_instances()) == 12
            assert len(r.get_folders()) == 2
            assert len(r.get_properties()) == 23
            assert len(r.get_tags()) == 10
    finally:
        panoptic.close_project(run.project_id)


def test_second_concurrent_migration_is_rejected(panoptic, tmp_path):
    proj = _copy_fixture('v7c', tmp_path / 'src')
    panoptic.legacy._active = 'someone-else'
    panoptic.legacy._runs['someone-else'] = type(
        'R', (), {'name': 'Other', 'stage': 'read-legacy'})()
    try:
        with pytest.raises(ValueError, match='already running'):
            panoptic.legacy.migrate(str(proj), str(tmp_path / 'dest'))
    finally:
        panoptic.legacy._active = None


def test_unreadable_project_db_says_grant_access(panoptic, tmp_path):
    """A TCC-style denial must never read as "the files are missing"."""
    datadir = tmp_path / 'legacy_home'
    datadir.mkdir()
    proj = _copy_fixture('v7c', tmp_path / 'locked')
    db = proj / 'panoptic.db'
    os.chmod(db, 0o000)
    _make_legacy_home_db(datadir / 'panoptic.db', [(1, 'Locked', str(proj))])
    try:
        info = panoptic.legacy.discover(base=datadir).projects[0]
    finally:
        os.chmod(db, 0o644)
    assert info.exists is True
    assert 'Full Disk Access' in info.problem
    assert 'missing' not in info.problem
