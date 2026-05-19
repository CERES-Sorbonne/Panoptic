"""Integration tests for Panoptic2 — lifecycle, project management, users, plugins."""
import shutil
from pathlib import Path
from typing import Any, Generator

import pytest

from panoptic2.core.panoptic.panoptic import Panoptic2
from panoptic2.core.project.project import Project2


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def panoptic(tmp_path: Path) -> Generator[Panoptic2, Any, None]:
    db_path = tmp_path / 'panoptic' / 'panoptic.db'
    p = Panoptic2(db_path)
    p.start()
    yield p
    p.close()


@pytest.fixture
def project_folder(tmp_path: Path) -> Path:
    folder = tmp_path / 'my_project'
    folder.mkdir()
    return folder


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

def test_start_creates_db(tmp_path: Path):
    db_path = tmp_path / 'panoptic' / 'panoptic.db'
    p = Panoptic2(db_path)
    p.start()
    assert db_path.exists()
    assert p.db is not None
    p.close()
    assert p.db is None


def test_context_manager(tmp_path: Path):
    db_path = tmp_path / 'panoptic.db'
    with Panoptic2(db_path) as p:
        assert p.db is not None
    assert p.db is None


# ---------------------------------------------------------------------------
# Project management
# ---------------------------------------------------------------------------

def test_create_project(panoptic: Panoptic2, project_folder: Path):
    key = panoptic.create_project('My Project', project_folder)

    assert key.name == 'My Project'
    assert key.path == str(project_folder)
    assert key.id  # non-empty UUID
    assert (project_folder / 'project.db').exists(), 'project.db missing'
    assert (project_folder / 'data.db').exists(),    'data.db missing'
    assert (project_folder / 'media.db').exists(),   'media.db missing'


def test_create_project_duplicate_path_raises(panoptic: Panoptic2, project_folder: Path):
    panoptic.create_project('First', project_folder)
    with pytest.raises(ValueError, match='already registered'):
        panoptic.create_project('Second', project_folder)


def test_get_projects_returns_created(panoptic: Panoptic2, project_folder: Path):
    assert panoptic.get_projects() == []
    key = panoptic.create_project('P', project_folder)
    projects = panoptic.get_projects()
    assert len(projects) == 1
    assert projects[0].id == key.id


def test_import_project(panoptic: Panoptic2, tmp_path: Path):
    # Seed a project folder using Project2 directly
    folder = tmp_path / 'existing_project'
    with Project2(folder) as proj:
        uid = proj.config.id

    key = panoptic.import_project(folder)
    assert key.id == uid
    assert key.name == folder.name
    assert panoptic.get_projects()[0].id == uid


def test_import_project_no_db_raises(panoptic: Panoptic2, tmp_path: Path):
    empty = tmp_path / 'empty'
    empty.mkdir()
    with pytest.raises(ValueError, match='no project.db'):
        panoptic.import_project(empty)


def test_import_project_duplicate_path_raises(panoptic: Panoptic2, tmp_path: Path):
    folder = tmp_path / 'proj'
    with Project2(folder):
        pass
    panoptic.import_project(folder)
    with pytest.raises(ValueError, match='already registered'):
        panoptic.import_project(folder)


def test_load_project_returns_project2(panoptic: Panoptic2, project_folder: Path):
    key = panoptic.create_project('P', project_folder)
    project = panoptic.load_project(key.id)
    assert isinstance(project, Project2)
    assert project.config.id == key.id


def test_load_project_same_instance_returned_twice(panoptic: Panoptic2, project_folder: Path):
    key = panoptic.create_project('P', project_folder)
    p1 = panoptic.load_project(key.id)
    p2 = panoptic.load_project(key.id)
    assert p1 is p2


def test_load_project_unknown_uid_raises(panoptic: Panoptic2):
    with pytest.raises(ValueError, match='not registered'):
        panoptic.load_project('nonexistent-id')


def test_get_project_before_load_returns_none(panoptic: Panoptic2, project_folder: Path):
    key = panoptic.create_project('P', project_folder)
    assert panoptic.get_project(key.id) is None


def test_get_project_after_load_returns_instance(panoptic: Panoptic2, project_folder: Path):
    key = panoptic.create_project('P', project_folder)
    panoptic.load_project(key.id)
    assert panoptic.get_project(key.id) is not None


def test_close_project_removes_from_loaded(panoptic: Panoptic2, project_folder: Path):
    key = panoptic.create_project('P', project_folder)
    panoptic.load_project(key.id)
    assert panoptic.get_project(key.id) is not None
    panoptic.close_project(key.id)
    assert panoptic.get_project(key.id) is None


def test_close_project_not_loaded_is_noop(panoptic: Panoptic2, project_folder: Path):
    key = panoptic.create_project('P', project_folder)
    panoptic.close_project(key.id)  # should not raise


def test_delete_project_removes_registration(panoptic: Panoptic2, project_folder: Path):
    key = panoptic.create_project('P', project_folder)
    panoptic.delete_project(key.id)
    assert panoptic.get_projects() == []


def test_delete_project_with_files_removes_folder(panoptic: Panoptic2, project_folder: Path):
    key = panoptic.create_project('P', project_folder)
    assert project_folder.exists()
    panoptic.delete_project(key.id, delete_files=True)
    assert not project_folder.exists()


def test_delete_project_without_files_keeps_folder(panoptic: Panoptic2, project_folder: Path):
    key = panoptic.create_project('P', project_folder)
    panoptic.delete_project(key.id, delete_files=False)
    assert project_folder.exists()


def test_update_project_name(panoptic: Panoptic2, project_folder: Path):
    key = panoptic.create_project('Old Name', project_folder)
    updated = panoptic.update_project(key.id, name='New Name')
    assert updated.name == 'New Name'
    assert panoptic.get_projects()[0].name == 'New Name'


def test_update_project_excluded_plugins(panoptic: Panoptic2, project_folder: Path):
    key = panoptic.create_project('P', project_folder)
    updated = panoptic.update_project(key.id, excluded_plugins=['plugin_a'])
    assert updated.excluded_plugins == ['plugin_a']


def test_load_project_uuid_mismatch_raises(panoptic: Panoptic2, tmp_path: Path):
    """Detect when a project folder has been replaced (UUID mismatch)."""
    folder_a = tmp_path / 'a'
    folder_b = tmp_path / 'b'
    key_a = panoptic.create_project('A', folder_a)

    # Create a second project in folder_b, then overwrite folder_a with it
    with Project2(folder_b):
        pass
    shutil.rmtree(folder_a)
    shutil.copytree(folder_b, folder_a)

    with pytest.raises(ValueError, match='ID mismatch'):
        panoptic.load_project(key_a.id)


def test_panoptic_close_closes_loaded_projects(tmp_path: Path, project_folder: Path):
    db_path = tmp_path / 'panoptic.db'
    p = Panoptic2(db_path)
    p.start()
    key = p.create_project('P', project_folder)
    p.load_project(key.id)
    assert p.get_project(key.id) is not None
    p.close()
    # After close the db is gone; no in-memory projects remain
    assert p.db is None


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------

def test_create_user(panoptic: Panoptic2):
    user = panoptic.create_user('alice', description='test user')
    assert user.name == 'alice'
    assert user.id  # non-empty


def test_get_users(panoptic: Panoptic2):
    assert panoptic.get_users() == []
    panoptic.create_user('alice')
    panoptic.create_user('bob')
    names = {u.name for u in panoptic.get_users()}
    assert names == {'alice', 'bob'}


def test_create_user_duplicate_name_raises(panoptic: Panoptic2):
    panoptic.create_user('alice')
    with pytest.raises(ValueError, match='already exists'):
        panoptic.create_user('alice')


def test_get_user_by_name(panoptic: Panoptic2):
    panoptic.create_user('alice')
    user = panoptic.get_user_by_name('alice')
    assert user is not None
    assert user.name == 'alice'


def test_get_user_by_name_missing_returns_none(panoptic: Panoptic2):
    assert panoptic.get_user_by_name('nobody') is None


def test_delete_user(panoptic: Panoptic2):
    user = panoptic.create_user('alice')
    panoptic.delete_user(user.id)
    assert panoptic.get_user_by_name('alice') is None


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

def test_login_returns_token(panoptic: Panoptic2):
    panoptic.create_user('alice', password='secret')
    token = panoptic.login('alice', 'secret')
    assert isinstance(token, str) and len(token) > 0


def test_login_wrong_password_raises(panoptic: Panoptic2):
    panoptic.create_user('alice', password='secret')
    with pytest.raises(ValueError, match='Invalid credentials'):
        panoptic.login('alice', 'wrong')


def test_login_unknown_user_raises(panoptic: Panoptic2):
    with pytest.raises(ValueError, match='Invalid credentials'):
        panoptic.login('nobody', 'pw')


def test_get_user_from_token(panoptic: Panoptic2):
    panoptic.create_user('alice', password='pw')
    token = panoptic.login('alice', 'pw')
    user = panoptic.get_user_from_token(token)
    assert user is not None
    assert user.name == 'alice'


def test_get_user_from_invalid_token_returns_none(panoptic: Panoptic2):
    assert panoptic.get_user_from_token('bad-token') is None


def test_logout_invalidates_token(panoptic: Panoptic2):
    panoptic.create_user('alice', password='pw')
    token = panoptic.login('alice', 'pw')
    panoptic.logout(token)
    assert panoptic.get_user_from_token(token) is None


def test_each_login_returns_distinct_token(panoptic: Panoptic2):
    panoptic.create_user('alice', password='pw')
    t1 = panoptic.login('alice', 'pw')
    t2 = panoptic.login('alice', 'pw')
    assert t1 != t2


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

def test_get_state(panoptic: Panoptic2, project_folder: Path):
    key = panoptic.create_project('P', project_folder)
    panoptic.load_project(key.id)

    state = panoptic.get_state()
    assert any(p.id == key.id for p in state.projects)
    assert key.id in state.loaded_project_ids
