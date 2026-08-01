"""Read-only property enforcement at the route layer.

System properties (system_key set) and properties whose owner declared access='read'
must be refused by /commit/upsert and /commit/delete, and a partial property update
must never clobber the fields the client did not send.
"""
import pytest
from fastapi import HTTPException

from panoptic.core.databases.data.models import Property, UpsertCommit
from panoptic.core.databases.data.system_properties import is_readonly
from panoptic.core.databases.entity_schema import OP_CREATE
from panoptic.core.project.project import Project
from panoptic.routes.project_routes import (
    DeleteRequest, UpsertRequest, delete_commit_route, upsert_commit_route,
)


@pytest.fixture
def project(tmp_path):
    p = Project(tmp_path / 'proj')
    p.start()
    yield p
    p.close()


def _props(project) -> dict[str, Property]:
    return {p.name: p for p in project.get_properties()}


def _system_prop(project) -> Property:
    return next(p for p in project.get_properties() if p.system_key == 'width')


def _make_prop(project, name='mine', access='write') -> Property:
    pid = project.allocate_properties(1)
    if not isinstance(pid, int):
        pid = list(pid)[0]
    commit = UpsertCommit()
    commit.properties[pid] = Property(
        id=pid, dtype='text', mode='sha1', name=name, access=access,
        tag_list_id=pid, commit_id=0, operation=OP_CREATE,
    )
    project.apply_upsert_commit('plugin', commit)
    return next(p for p in project.get_properties() if p.id == pid)


# ---------------------------------------------------------------------------
# is_readonly
# ---------------------------------------------------------------------------

def test_is_readonly_flags():
    assert is_readonly(Property(id=1, system_key='width', access='read'))
    assert is_readonly(Property(id=1, system_key='width', access='write'))  # system wins
    assert is_readonly(Property(id=1, access='read'))
    assert not is_readonly(Property(id=1, access='write'))
    assert not is_readonly(Property(id=1))


# ---------------------------------------------------------------------------
# System properties
# ---------------------------------------------------------------------------

def test_system_properties_are_readonly(project):
    sys_props = [p for p in project.get_properties() if p.system_key]
    assert sys_props
    assert all(is_readonly(p) for p in sys_props)


def test_upsert_rename_system_property_is_refused(project):
    sp = _system_prop(project)
    req = UpsertRequest(properties=[{'id': sp.id, 'name': 'hacked'}])

    with pytest.raises(HTTPException) as e:
        upsert_commit_route(req, project)
    assert e.value.status_code == 403

    after = next(p for p in project.get_properties() if p.id == sp.id)
    assert after.name == sp.name
    assert after.system_key == sp.system_key  # the regression this guards against
    assert after.access == 'read'


def test_upsert_values_on_system_property_is_refused(project):
    sp = _system_prop(project)
    req = UpsertRequest(instance_values=[{'property_id': sp.id, 'instance_id': 1, 'value': 42}])
    with pytest.raises(HTTPException) as e:
        upsert_commit_route(req, project)
    assert e.value.status_code == 403


def test_upsert_tag_on_system_property_is_refused(project):
    sp = _system_prop(project)
    req = UpsertRequest(tags=[{'id': -1, 'property_id': sp.id, 'value': 'nope'}])
    with pytest.raises(HTTPException) as e:
        upsert_commit_route(req, project)
    assert e.value.status_code == 403


def test_delete_system_property_is_refused(project):
    sp = _system_prop(project)
    with pytest.raises(HTTPException) as e:
        delete_commit_route(DeleteRequest(empty_properties=[sp.id]), project)
    assert e.value.status_code == 403
    assert any(p.id == sp.id for p in project.get_properties())


def test_refused_commit_allocates_no_property_id(project):
    sp = _system_prop(project)
    before = project.allocate_properties(0)
    req = UpsertRequest(properties=[
        {'id': -1, 'name': 'new', 'type': 'text'},
        {'id': sp.id, 'name': 'hacked'},
    ])
    with pytest.raises(HTTPException):
        upsert_commit_route(req, project)
    assert project.allocate_properties(0) == before
    assert 'new' not in _props(project)


# ---------------------------------------------------------------------------
# Plugin-declared read-only properties
# ---------------------------------------------------------------------------

def test_plugin_readonly_property_refused_by_routes(project):
    prop = _make_prop(project, name='cluster', access='read')

    with pytest.raises(HTTPException) as e:
        upsert_commit_route(UpsertRequest(properties=[{'id': prop.id, 'name': 'x'}]), project)
    assert e.value.status_code == 403

    with pytest.raises(HTTPException) as e:
        upsert_commit_route(
            UpsertRequest(instance_values=[{'property_id': prop.id, 'instance_id': 1, 'value': 1}]),
            project)
    assert e.value.status_code == 403

    with pytest.raises(HTTPException) as e:
        delete_commit_route(DeleteRequest(empty_properties=[prop.id]), project)
    assert e.value.status_code == 403


def test_plugin_can_still_write_its_readonly_property(project):
    """The guard lives at the route layer only — the owner keeps write access."""
    prop = _make_prop(project, name='cluster', access='read')
    commit = UpsertCommit()
    commit.properties[prop.id] = Property(
        id=prop.id, dtype='text', mode='sha1', name='cluster2', access='read',
        tag_list_id=prop.id, commit_id=0, operation=OP_CREATE,
    )
    project.apply_upsert_commit('plugin', commit)
    assert next(p for p in project.get_properties() if p.id == prop.id).name == 'cluster2'


def test_plugin_interface_add_property_readonly(project, tmp_path):
    from panoptic.core.plugin.plugin_interface import PluginProjectInterface

    iface = PluginProjectInterface(
        'test_plugin', tmp_path, project.data_db_path, project.media_db_path,
        project.project_db_path, project.task_manager, project.action,
        lambda *_: None, lambda *_: None,
    )
    ro = iface.add_property('score', 'number', readonly=True)
    rw = iface.add_property('note', 'text')

    assert ro.access == 'read' and is_readonly(ro)
    assert rw.access == 'write' and not is_readonly(rw)
    stored = {p.id: p for p in project.get_properties()}
    assert stored[ro.id].name == 'score'
    assert stored[rw.id].name == 'note'

    with pytest.raises(HTTPException):
        upsert_commit_route(UpsertRequest(properties=[{'id': ro.id, 'name': 'x'}]), project)


# ---------------------------------------------------------------------------
# Normal properties keep working
# ---------------------------------------------------------------------------

def test_partial_update_preserves_untouched_fields(project):
    prop = _make_prop(project, name='mine')
    upsert_commit_route(UpsertRequest(properties=[{'id': prop.id, 'name': 'renamed'}]), project)

    after = next(p for p in project.get_properties() if p.id == prop.id)
    assert after.name == 'renamed'
    assert after.dtype == prop.dtype      # not reset to 'text'
    assert after.mode == prop.mode        # not reset to 'sha1'
    assert after.tag_list_id == prop.tag_list_id
    assert after.access == 'write'
    assert after.system_key is None


def test_create_update_and_delete_normal_property(project):
    res = upsert_commit_route(
        UpsertRequest(properties=[{'id': -1, 'name': 'note', 'type': 'text', 'mode': 'sha1'}]),
        project)
    pid = res['properties'][0]['id']

    upsert_commit_route(UpsertRequest(properties=[{'id': pid, 'name': 'note2'}]), project)
    assert next(p for p in project.get_properties() if p.id == pid).name == 'note2'

    delete_commit_route(DeleteRequest(empty_properties=[pid]), project)
    assert not any(p.id == pid for p in project.get_properties())
