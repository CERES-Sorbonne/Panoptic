"""The public plugin API: PluginProjectInterface helpers, Task progress, ActionResult shortcuts.

Run from panoptic_back/:
    .venv/bin/python -m pytest test/test_plugin_api.py
"""
import threading

import numpy as np
import pytest

from panoptic.core.databases.data.data_reader import DataReader
from panoptic.core.databases.data.data_writer import DataWriter
from panoptic.core.databases.data.models import DeleteCommit, File, Folder, Instance
from panoptic.core.databases.media.models import Image, ImageType, Vector
from panoptic.core.project.project import Project
from panoptic.core.task.task import Task
from panoptic.core.task.task_manager import TaskManager
from panoptic.models.action_models import ActionContext, ActionResult, NotifType


@pytest.fixture
def project(tmp_path):
    p = Project(tmp_path / 'proj')
    p.start()
    yield p
    p.close()


@pytest.fixture
def iface(project):
    return project.make_plugin_interface('plugin')


def _structure(project):
    """Folders 1 > 2 > 3 and 4; one file per folder; file 2 has two instances."""
    with DataWriter(str(project.data_db_path)) as w:
        w.add_structural(
            folders=[Folder(id=1, source_id=None, path='/a', name='a', parent=None),
                     Folder(id=2, source_id=None, path='/a/b', name='b', parent=1),
                     Folder(id=3, source_id=None, path='/a/b/c', name='c', parent=2),
                     Folder(id=4, source_id=None, path='/d', name='d', parent=None)],
            files=[File(id=10 + i, name=f'f{i}', folder_id=i, sha1=f's{i}') for i in (1, 2, 3, 4)],
            instances=[Instance(id=101, file_id=11, sha1='s1'),
                       Instance(id=102, file_id=12, sha1='s2'),
                       Instance(id=103, file_id=12, sha1='s2'),
                       Instance(id=104, file_id=13, sha1='s3'),
                       Instance(id=105, file_id=14, sha1='s4')],
        )


def _own(iface):
    """Properties other than the system ones every project has."""
    return [p for p in iface.get_properties() if p.system_key is None]


def _commit_count(project) -> int:
    with DataReader(str(project.data_db_path)) as r:
        return len(r.get_commits())


def _sha1_tags(project, prop_id) -> dict[str, set[int]]:
    with DataReader(str(project.data_db_path)) as r:
        rows = r.get_sha1_tag_values(property_id=prop_id)
    out: dict[str, set[int]] = {}
    for row in rows:
        out.setdefault(row.sha1, set()).add(row.tag_id)
    return out


# ---------------------------------------------------------------------------
# Selection and folders
# ---------------------------------------------------------------------------

def test_instances_and_sha1s_of_context(project, iface):
    _structure(project)
    ctx = ActionContext(instance_ids=[104, 102, 103, 104])
    assert [i.id for i in iface.instances_of(ctx)] == [104, 102, 103]
    assert iface.sha1s_of(ctx) == ['s3', 's2']
    # No selection means every instance
    assert len(iface.instances_of(ActionContext())) == 5
    assert sorted(iface.sha1s_of(ActionContext(instance_ids=[]))) == ['s1', 's2', 's3', 's4']


def test_instances_under_folder(project, iface):
    _structure(project)
    assert sorted(i.id for i in iface.get_instances_under_folder(1)) == [101, 102, 103, 104]
    assert sorted(i.id for i in iface.get_instances_under_folder(3)) == [104]
    assert sorted(i.id for i in iface.get_instances_under_folder(4)) == [105]
    assert len(iface.get_instances_under_folder(None)) == 5
    assert iface.get_instances_under_folder(999) == []


# ---------------------------------------------------------------------------
# Stored images and vectors
# ---------------------------------------------------------------------------

def test_image_types_and_bytes(project, iface):
    types = {t.name: t for t in iface.get_image_types()}
    small, large = types['small'], types['large']  # 256 and 1024 px in a new project
    assert iface.pick_image_type().id == large.id
    assert iface.pick_image_type(min_size=200).id == small.id
    assert iface.pick_image_type(min_size=512).id == large.id
    assert iface.pick_image_type(min_size=4096).id == large.id   # none big enough: largest

    project.upsert_images([Image(type_id=small.id, sha1='a', data=b'A'),
                           Image(type_id=small.id, sha1='b', data=b'B'),
                           Image(type_id=large.id, sha1='a', data=b'AA')])
    assert iface.get_image_bytes(small.id, ['a', 'b', 'missing']) == {'a': b'A', 'b': b'B'}
    assert iface.get_image_bytes(large.id, ['a', 'b']) == {'a': b'AA'}
    assert iface.get_image_bytes(large.id, []) == {}


def test_pick_image_type_without_sizes(project, iface):
    with project._media_db() as mdb:
        for t in mdb.get_image_types():
            mdb.delete_image_type(t.id)
        mdb.upsert_image_type(ImageType(id=7, name='orig', format='jpeg', width=None, height=None))
    assert iface.pick_image_type(min_size=100).id == 7


def test_vector_sha1s(project, iface):
    project.upsert_vectors([Vector(type_id=1, sha1='a', data=np.zeros(3, dtype=np.float32)),
                            Vector(type_id=1, sha1='b', data=np.zeros(3, dtype=np.float32)),
                            Vector(type_id=2, sha1='c', data=np.zeros(3, dtype=np.float32))])
    assert iface.get_vector_sha1s(1) == {'a', 'b'}
    assert iface.get_vector_sha1s(3) == set()


# ---------------------------------------------------------------------------
# ensure_property
# ---------------------------------------------------------------------------

def test_ensure_property_is_found_again(project, iface):
    prop = iface.ensure_property('score', 'Score', 'number', group='Faces')
    assert iface.ensure_property('score', 'Other name', 'number', group='Faces').id == prop.id

    # A new interface (plugin restart) finds it through project.db, even after a rename
    project.apply_upsert_commit('ui', _rename(prop, 'Renamed'))
    again = project.make_plugin_interface('plugin').ensure_property('score', 'Score', 'number')
    assert again.id == prop.id and again.name == 'Renamed'

    # Another plugin has its own keys
    assert project.make_plugin_interface('other').ensure_property('score', 'Score', 'number').id != prop.id


def _rename(prop, name):
    from panoptic.core.databases.data.models import UpsertCommit
    import msgspec
    commit = UpsertCommit()
    commit.properties[prop.id] = msgspec.structs.replace(prop, name=name)
    return commit


def test_ensure_property_groups(project, iface):
    a = iface.ensure_property('a', 'A', 'number', group='Faces')
    b = iface.ensure_property('b', 'B', 'text', group='Faces')
    groups = iface.get_property_groups()
    assert len(groups) == 1 and a.property_group_id == b.property_group_id == groups[0].id
    assert iface.ensure_property('c', 'C', 'text').property_group_id is None

    # A deleted group is created again for the next new property
    iface.apply_delete_commit(DeleteCommit(property_groups={groups[0].id}))
    d = iface.ensure_property('d', 'D', 'text', group='Faces')
    assert d.property_group_id not in (None, groups[0].id)


def test_ensure_property_recreated_when_deleted_or_changed(iface):
    prop = iface.ensure_property('p', 'P', 'number', readonly=True)
    assert prop.access == 'read'

    iface.apply_delete_commit(DeleteCommit(properties={prop.id}))
    recreated = iface.ensure_property('p', 'P', 'number')
    assert recreated.id != prop.id

    # Another dtype: a new property, the old one is left in place
    changed = iface.ensure_property('p', 'P', 'multi_tags')
    assert changed.id != recreated.id and changed.dtype == 'multi_tags'
    assert {p.id for p in _own(iface)} == {recreated.id, changed.id}
    assert iface.ensure_property('p', 'P', 'multi_tags').id == changed.id


def test_adopt_property(project, iface):
    # Created before the plugin had ensure_property, e.g. ids from its own cache file
    group = iface.add_property_group('Faces')
    old = iface.add_property('Persons', 'multi_tags', property_group_id=group.id)

    assert iface.adopt_property('persons', old.id, group='Faces', group_id=group.id).id == old.id
    assert iface.ensure_property('persons', 'Persons', 'multi_tags', group='Faces').id == old.id
    # The adopted group is reused for the plugin's next new property
    assert iface.ensure_property('score', 'Score', 'number', group='Faces').property_group_id == group.id

    # Again after migration: the live mapping is kept
    other = iface.add_property('Other', 'multi_tags')
    assert iface.adopt_property('persons', other.id).id == old.id
    assert iface.ensure_property('persons', 'Persons', 'multi_tags').id == old.id


def test_adopt_dead_property_records_nothing(project, iface):
    group = iface.add_property_group('Faces')
    prop = iface.add_property('Score', 'number')
    iface.apply_delete_commit(DeleteCommit(properties={prop.id}))

    assert iface.adopt_property('score', prop.id, group='Faces', group_id=group.id) is None
    created = iface.ensure_property('score', 'Score', 'number', group='Faces')
    assert created.id != prop.id
    assert created.property_group_id != group.id   # the group was not recorded either

    # A mapped key whose property was deleted can be adopted again
    live = iface.add_property('Score 2', 'number')
    iface.apply_delete_commit(DeleteCommit(properties={created.id}))
    assert iface.adopt_property('score', live.id).id == live.id
    assert iface.ensure_property('score', 'Score', 'number').id == live.id


def test_adopt_property_skips_dead_group(iface):
    group = iface.add_property_group('Faces')
    prop = iface.add_property('Score', 'number')
    iface.apply_delete_commit(DeleteCommit(property_groups={group.id}))
    assert iface.adopt_property('score', prop.id, group='Faces', group_id=group.id).id == prop.id
    new = iface.ensure_property('other', 'Other', 'number', group='Faces')
    assert new.property_group_id not in (None, group.id)


def test_ensure_property_from_threads(iface):
    ids, barrier = [], threading.Barrier(8)

    def run():
        barrier.wait()
        ids.append(iface.ensure_property('k', 'K', 'number', group='G').id)

    threads = [threading.Thread(target=run) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(set(ids)) == 1
    assert len(_own(iface)) == 1 and len(iface.get_property_groups()) == 1


# ---------------------------------------------------------------------------
# ensure_tags
# ---------------------------------------------------------------------------

def test_ensure_tags(project, iface):
    prop = iface.ensure_property('persons', 'Persons', 'multi_tags')
    before = _commit_count(project)
    ids = iface.ensure_tags(prop.id, ['Ann', 'Bob', 'Ann'], color=lambda label: len(label))
    assert list(ids) == ['Ann', 'Bob'] and _commit_count(project) == before + 1
    tags = {t.value: t for t in iface.get_tags(list_id=prop.tag_list_id)}
    assert {v: t.id for v, t in tags.items()} == ids
    assert tags['Ann'].color == 3

    # Known labels: same ids, no commit
    assert iface.ensure_tags(prop.id, ['Bob']) == {'Bob': ids['Bob']}
    assert _commit_count(project) == before + 1

    new = iface.ensure_tags(prop.id, ['Cy'])
    assert 0 <= next(t for t in iface.get_tags() if t.id == new['Cy']).color <= 11
    assert iface.ensure_tags(prop.id, ['Dee'], color=5)['Dee'] in {
        t.id for t in iface.get_tags() if t.color == 5}

    with pytest.raises(ValueError):
        iface.ensure_tags(iface.ensure_property('n', 'N', 'number').id, ['x'])


def test_ensure_tags_from_threads(iface):
    prop = iface.ensure_property('persons', 'Persons', 'multi_tags')
    barrier = threading.Barrier(6)

    def run():
        barrier.wait()
        iface.ensure_tags(prop.id, ['Ann', 'Bob', 'Cy'])

    threads = [threading.Thread(target=run) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(t.value for t in iface.get_tags(list_id=prop.tag_list_id)) == ['Ann', 'Bob', 'Cy']


# ---------------------------------------------------------------------------
# set_*_values
# ---------------------------------------------------------------------------

def test_set_sha1_values_scalar(project, iface):
    prop = iface.ensure_property('score', 'Score', 'number')
    assert iface.set_sha1_values(prop.id, {'a': 1, 'b': 2}) is not None
    values = {v.sha1: v.value for v in iface.get_sha1_values(property_id=prop.id)}
    assert values == {'a': 1, 'b': 2}

    # Same values again: no commit
    assert iface.set_sha1_values(prop.id, {'a': 1, 'b': 2}) is None
    assert iface.set_sha1_values(prop.id, {}) is None

    # None clears the cell, as the UI does
    iface.set_sha1_values(prop.id, {'a': None})
    values = {v.sha1: v.value for v in iface.get_sha1_values(property_id=prop.id)}
    assert values == {'a': None, 'b': 2}


def test_set_sha1_values_tags(project, iface):
    prop = iface.ensure_property('persons', 'Persons', 'multi_tags')
    ann = iface.ensure_tags(prop.id, ['Ann'])['Ann']
    before = _commit_count(project)

    iface.set_sha1_values(prop.id, {'a': ['Bob', ann], 'b': 'Cy', 'c': ann}, tag_color=4)
    assert _commit_count(project) == before + 1   # new tags and values in one commit
    tags = {t.value: t for t in iface.get_tags(list_id=prop.tag_list_id)}
    assert tags['Bob'].color == tags['Cy'].color == 4
    assert _sha1_tags(project, prop.id) == {
        'a': {tags['Ann'].id, tags['Bob'].id}, 'b': {tags['Cy'].id}, 'c': {ann}}

    # [] and None both remove every tag of the cell
    iface.set_sha1_values(prop.id, {'a': [], 'b': None})
    assert _sha1_tags(project, prop.id) == {'c': {ann}}


def test_set_sha1_values_mono_tag(project, iface):
    prop = iface.ensure_property('label', 'Label', 'tag')
    iface.set_sha1_values(prop.id, {'a': 'cat'})
    iface.set_sha1_values(prop.id, {'a': 'dog'})
    dog = iface.ensure_tags(prop.id, ['dog'])['dog']
    assert _sha1_tags(project, prop.id) == {'a': {dog}}


def test_set_sha1_values_many_is_one_commit(project, iface):
    props = [iface.ensure_property(f'p{i}', f'P{i}', 'number') for i in range(5)]
    tags = iface.ensure_property('persons', 'Persons', 'multi_tags')
    sha1s = [f'{i:040x}' for i in range(2000)]
    before = _commit_count(project)
    payload = {p.id: {s: i for i, s in enumerate(sha1s)} for p in props}
    payload[tags.id] = {s: [f'person{i % 7}'] for i, s in enumerate(sha1s)}
    iface.set_sha1_values_many(payload)
    assert _commit_count(project) == before + 1
    assert len(iface.get_sha1_values(property_id=props[4].id)) == 2000
    assert len(_sha1_tags(project, tags.id)) == 2000
    assert len(iface.get_tags(list_id=tags.tag_list_id)) == 7


def test_set_instance_values(project, iface):
    prop = iface.ensure_property('note', 'Note', 'text', mode='id')
    tags = iface.ensure_property('kind', 'Kind', 'multi_tags', mode='id')
    iface.set_instance_values_many({prop.id: {1: 'x', 2: 'y'}, tags.id: {1: ['k']}})
    assert {v.instance_id: v.value for v in iface.get_instance_values(property_id=prop.id)} == {
        1: 'x', 2: 'y'}
    with DataReader(str(project.data_db_path)) as r:
        assert [(v.instance_id, v.tag_id) for v in r.get_instance_tag_values(property_id=tags.id)] == [
            (1, iface.ensure_tags(tags.id, ['k'])['k'])]


def test_set_values_checks_the_property(iface):
    sha1_prop = iface.ensure_property('s', 'S', 'number')
    id_prop = iface.ensure_property('i', 'I', 'number', mode='id')
    with pytest.raises(ValueError):
        iface.set_sha1_values(id_prop.id, {'a': 1})
    with pytest.raises(ValueError):
        iface.set_instance_values(sha1_prop.id, {1: 1})
    with pytest.raises(KeyError):
        iface.set_sha1_values(9999, {'a': 1})


def test_set_values_fire_on_commit(project, iface):
    fired = []
    project._on_commit = lambda: fired.append(1)
    prop = iface.ensure_property('score', 'Score', 'number')
    fired.clear()
    iface.set_sha1_values(prop.id, {'a': 1})
    assert fired == [1]


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

def test_on_vector_type_delete(project, iface):
    seen = []
    iface.on_vector_type_delete(seen.append)
    project.delete_vector_type(3)
    assert seen == [3]

    # Dropped with the plugin's other callbacks when it is stopped
    project.unload_plugin('plugin')
    project.delete_vector_type(4)
    assert seen == [3]


# ---------------------------------------------------------------------------
# Task progress
# ---------------------------------------------------------------------------

class _Progress(Task):
    def __init__(self, threads: int = 4, per_thread: int = 500):
        super().__init__()
        self.threads, self.per_thread = threads, per_thread

    def start(self):
        self.set_total(self.threads * self.per_thread)
        self.restart_clock()

        def work():
            for i in range(self.per_thread):
                self.advance() if i % 5 else self.add_failed()

        workers = [threading.Thread(target=work) for _ in range(self.threads)]
        for w in workers:
            w.start()
        for w in workers:
            w.join()


def test_task_progress_helpers_notify():
    task = _Progress()
    states = []
    task.on_progress(lambda s: states.append((s.total, s.done, s.failed)))
    task.set_total(10)
    task.advance()
    task.advance(3)
    task.add_failed(2)
    assert states == [(10, 0, 0), (10, 1, 0), (10, 4, 0), (10, 4, 2)]

    task.state.started_at = 0.0
    task.restart_clock()
    assert task.state.started_at > 0 and len(states) == 5


def test_task_progress_from_threads_and_finish_without_plugin_code():
    manager = TaskManager()
    try:
        task = manager.add_task(_Progress(threads=8, per_thread=1000))
        task.wait()
        state = task.state
        assert (state.total, state.done, state.failed) == (8000, 6400, 1600)
        # The task never touched running/finished: the TaskManager ends it
        assert state.finished and not state.running
    finally:
        manager.close()


# ---------------------------------------------------------------------------
# ActionResult shortcuts and the public module
# ---------------------------------------------------------------------------

def test_action_result_shortcuts():
    err = ActionResult.error('Faces', 'No model')
    assert [(n.type, n.name, n.message) for n in err.notifs] == [(NotifType.ERROR, 'Faces', 'No model')]
    info = ActionResult.info('Done', name='Faces')
    assert [(n.type, n.name, n.message) for n in info.notifs] == [(NotifType.INFO, 'Faces', 'Done')]
    assert ActionResult.info('Done').notifs[0].name is None


def test_public_module_exports():
    import panoptic.plugin as api
    from panoptic.core.plugin.plugin import APlugin
    from panoptic.models.action_models import FolderPath

    assert api.APlugin is APlugin and api.FolderPath is FolderPath
    for name in api.__all__:
        assert getattr(api, name) is not None


def test_deprecated_db_aliases_still_work(iface):
    """deepfaune-panoptic-plugin still opens media.db / project.db through these."""
    with iface._media_db() as db:
        assert db.get_image_types()
    with iface._project_db() as pdb:
        assert isinstance(pdb.allocate_tags(1), int)
