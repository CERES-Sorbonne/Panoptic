"""Conversion of a data DB written before the generic-log rewrite.

`data/old_layout_data_db.sql` is a dump of a DB produced by the pre-rewrite writer
(commit 0f293319^): per-entity `_log` tables, a deleted property (14), a deleted tag (103)
and an undone edit of instance 1 / property 10 ('undone', inactive commit).
"""
import sqlite3
from pathlib import Path

import pytest

from panoptic.core.databases.data.data_reader import DataReader
from panoptic.core.databases.data.data_writer import DataWriter
from panoptic.core.databases.data.models import DataCommit, InstanceValue
from panoptic.core.project.conversion import (
    STATUS_OK, STATUS_OUTDATED, STATUS_MISSING, check_project, convert_project,
)

DUMP = Path(__file__).parent / 'data' / 'old_layout_data_db.sql'


@pytest.fixture
def old_project(tmp_path):
    conn = sqlite3.connect(tmp_path / 'data.db')
    conn.executescript(DUMP.read_text())
    conn.close()
    (tmp_path / 'project.db').touch()
    return tmp_path


def _reader(folder):
    r = DataReader(str(folder / 'data.db'))
    r.start()
    return r


def test_old_layout_is_outdated(old_project):
    assert check_project(old_project).status == STATUS_OUTDATED


def test_missing_project(tmp_path):
    assert check_project(tmp_path / 'nope').status == STATUS_MISSING


def test_new_project_is_ok(tmp_path):
    (tmp_path / 'project.db').touch()
    DataWriter(str(tmp_path / 'data.db')).start()
    assert check_project(tmp_path).status == STATUS_OK


def test_old_column_layout_is_outdated(old_project):
    conn = sqlite3.connect(old_project / 'data.db')
    conn.execute("ALTER TABLE file_sources DROP COLUMN sync_status")
    conn.close()
    assert check_project(old_project).status == STATUS_OUTDATED
    convert_project(old_project)
    assert check_project(old_project).status == STATUS_OK


def test_conversion_keeps_current_state(old_project):
    backup = convert_project(old_project)
    assert backup.is_file()
    assert check_project(old_project).status == STATUS_OK
    # the backup is a complete copy of the old DB
    assert check_project_backup(backup)

    r = _reader(old_project)
    assert sorted(p.id for p in r.get_properties()) == [10, 11, 12, 13, 15]
    assert [g.name for g in r.get_property_groups()] == ['grp']
    assert {t.id: t.parents for t in r.get_tags()} == {100: [], 101: [100], 102: []}
    values = {(v.property_id, v.instance_id): v.value for v in r.get_instance_values()}
    assert values == {(10, 1): 'hello', (11, 1): 3.5, (11, 2): 7}
    assert [(v.property_id, v.file_id, v.value) for v in r.get_file_values()] == [(15, 1, 'fv')]
    counts = {c['tag_id']: (c['instance_count'], c['sha1_count']) for c in r.get_tag_counts()}
    assert counts == {100: (1, 0), 101: (2, 0), 102: (0, 1)}

    conn = sqlite3.connect(old_project / 'data.db')
    # everything is baseline: nothing to undo
    assert conn.execute("SELECT count(*) FROM commits").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM entity_log WHERE commit_id != 0").fetchone()[0] == 0
    assert conn.execute("SELECT metadata, sync_status FROM file_sources").fetchone() == \
        ('{"a": 1}', '{"status": "ok"}')
    conn.close()


def test_first_edit_after_conversion_keeps_rows(old_project):
    convert_project(old_project)
    w = DataWriter(str(old_project / 'data.db'))
    w.start()
    w.apply_commit('t', DataCommit(instance_values=[
        InstanceValue(property_id=11, instance_id=1, value=4.0)]))
    r = _reader(old_project)
    assert len(r.get_properties()) == 5
    values = {(v.property_id, v.instance_id): v.value for v in r.get_instance_values()}
    assert values[(11, 1)] == 4.0 and values[(10, 1)] == 'hello'


def test_convert_refuses_current_layout(tmp_path):
    (tmp_path / 'project.db').touch()
    DataWriter(str(tmp_path / 'data.db')).start()
    with pytest.raises(ValueError):
        convert_project(tmp_path)


def check_project_backup(backup: Path) -> bool:
    conn = sqlite3.connect(backup)
    try:
        return conn.execute(
            "SELECT count(*) FROM sqlite_master WHERE name = 'properties_log'").fetchone()[0] == 1
    finally:
        conn.close()
