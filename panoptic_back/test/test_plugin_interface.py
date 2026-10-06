"""Writes made by a plugin through PluginProjectInterface.

They bypass Project, so the interface itself must fire the project's commit callback,
otherwise connected clients never fetch the new delta.
"""
import pytest

from panoptic.core.databases.data.models import DataCommit, Sha1Value
from panoptic.core.project.project import Project


@pytest.fixture
def project(tmp_path):
    p = Project(tmp_path / 'proj')
    p.start()
    yield p
    p.close()


@pytest.fixture
def fired(project):
    calls = []
    project._on_commit = lambda: calls.append(1)
    return calls


def test_plugin_writes_fire_on_commit(project, fired):
    plugin = project.make_plugin_interface('plugin')

    prop = plugin.add_property('score', 'number', 'sha1')
    assert len(fired) == 1

    plugin.apply_commit(DataCommit(sha1_values=[Sha1Value(property_id=prop.id, sha1='abc', value=3)]))
    assert len(fired) == 2


def test_add_property_group(project, fired):
    plugin = project.make_plugin_interface('plugin')

    group = plugin.add_property_group('Colors')
    prop = plugin.add_property('color_H', 'number', 'sha1', property_group_id=group.id)

    assert [(g.id, g.name) for g in plugin.get_property_groups()] == [(group.id, 'Colors')]
    assert next(p for p in project.get_properties() if p.id == prop.id).property_group_id == group.id
    assert len(fired) == 2
