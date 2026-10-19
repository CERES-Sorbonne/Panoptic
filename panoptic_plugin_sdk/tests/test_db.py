"""Direct DB helpers on an offline project (no backend)."""
import sqlite3

import numpy as np
import pytest

from panoptic_plugin import (
    DataCommit, InstanceValue, Map, OP_DELETE, Property, ProjectData, Sha1Value, Tag, Vector, VectorType,
)


@pytest.fixture
def data(project):
    d = ProjectData('MyPlugin', project)
    yield d
    d.close()


def test_structural_reads(data):
    insts = data.get_instances()
    assert [i.sha1 for i in insts] == ['sha_a1', 'sha_a2', 'sha_dup', 'sha_b1', 'sha_dup']
    assert [i.sha1 for i in data.instances(ids=[insts[0].id, insts[3].id])] == ['sha_a1', 'sha_b1']
    assert len(data.instances(sha1s=['sha_dup'])) == 2
    folders = data.get_folders()
    assert sorted(f.path for f in folders) == ['/data/a', '/data/b']
    a = next(f for f in folders if f.path == '/data/a')
    assert len(data.instances_under_folder(a.id)) == 3
    assert len(data.instances_under_folder(None)) == 5
    assert data.file_path('sha_b1') == '/data/b/b1.jpg'
    assert data.local_paths()['sha_a2'] == '/data/a/a2.jpg'


def test_chunked_filters(data):
    # more values than the SQLite variable budget: the query is chunked
    ids = list(range(1, 5000))
    assert len(data.get_instances(id=ids)) == 5


def test_add_property_and_values(data):
    prop = data.add_property('score', 'number', 'sha1', readonly=True)
    assert prop.id > 0 and prop.tag_list_id == prop.id and prop.access == 'read'
    res = data.set_values(prop.id, {'sha_a1': 1.5, 'sha_dup': 3})
    assert res.commit is not None and res.commit.source == 'MyPlugin'
    vals = data.values(prop.id)
    dups = [i.id for i in data.instances(sha1s=['sha_dup'])]
    assert vals[dups[0]] == 3 and vals[dups[1]] == 3
    assert len(vals) == 3
    # re-asserting the same values creates no commit
    assert data.set_values(prop.id, {'sha_a1': 1.5}).commit is None
    # instance subset
    first = data.get_instances()[0].id
    assert data.values(prop.id, [first]) == {first: 1.5}


def test_instance_mode_and_file_mode(data):
    p_id = data.add_property('note', 'text', 'id')
    p_file = data.add_property('fname', 'text', 'file')
    insts = data.get_instances()
    data.set_values(p_id.id, {insts[0].id: 'hello'})
    data.set_values(p_file.id, {insts[1].file_id: 'file2'})
    assert data.values(p_id.id) == {insts[0].id: 'hello'}
    assert data.values(p_file.id) == {insts[1].id: 'file2'}


def test_placeholders_and_tags(data):
    commit = DataCommit(
        properties=[Property(id=-1, dtype='multi_tags', mode='sha1', name='labels', access='write')],
        tags=[Tag(id=-1, list_id=-1, parents=[], value='cat'), Tag(id=-2, list_id=-1, parents=[-1], value='kitten')],
        sha1_values=[Sha1Value(property_id=-1, sha1='sha_a1', value=[-1, -2])],
    )
    res = data.commit(commit)
    pid = res.real_id('properties', -1)
    cat, kitten = res.real_id('tags', -1), res.real_id('tags', -2)
    tags = {t.id: t for t in data.get_tags()}
    assert tags[kitten].parents == [cat] and tags[cat].list_id == pid
    a1 = data.instances(sha1s=['sha_a1'])[0].id
    assert sorted(data.values(pid)[a1]) == sorted([cat, kitten])
    # deleting a tag removes its assignments (cascade)
    data.commit(DataCommit(tags=[Tag(id=kitten, operation=OP_DELETE)]))
    assert data.values(pid)[a1] == [cat]


def test_mono_tag_arity(data):
    res = data.commit(DataCommit(
        properties=[Property(id=-1, dtype='tag', mode='id', name='kind')],
        tags=[Tag(id=-1, list_id=-1, value='x'), Tag(id=-2, list_id=-1, value='y')]))
    pid, x, y = res.real_id('properties', -1), res.real_id('tags', -1), res.real_id('tags', -2)
    iid = data.get_instances()[0].id
    data.commit(DataCommit(instance_values=[InstanceValue(property_id=pid, instance_id=iid, value=[x])]))
    data.commit(DataCommit(instance_values=[InstanceValue(property_id=pid, instance_id=iid, value=[y])]))
    assert data.values(pid) == {iid: [y]}


def test_delete_property_cascades(data):
    prop = data.add_property('score', 'number', 'sha1')
    data.set_values(prop.id, {'sha_a1': 1})
    data.commit(DataCommit(properties=[Property(id=prop.id, operation=OP_DELETE)]))
    assert data.property(prop.id) is None
    assert data.get_sha1_values(property_id=prop.id) == []
    assert len(data.get_sha1_values(property_id=prop.id, state=-1)) == 1


def test_system_properties_rejected(data):
    with pytest.raises(ValueError):
        data.commit(DataCommit(properties=[Property(id=-1, dtype='text', mode='id', name='x', system_key='name')]))


def test_vectors_vector_types_maps(data):
    vt = data.upsert_vector_type(VectorType(id=-1, source='ignored', params={'model': 'm/x'}))
    assert vt.id > 0 and vt.source == 'MyPlugin' and str(vt) == f'MyPlugin_mx_{vt.id}'
    vecs = [Vector(type_id=vt.id, sha1=f's{i}', data=np.arange(4, dtype=np.float32) + i) for i in range(2500)]
    data.upsert_vectors(vecs)
    got = data.get_vectors(vt.id, sha1s=['s3'])
    assert got[0].data.dtype == np.float32 and list(got[0].data) == [3, 4, 5, 6]
    assert len(data.vector_sha1s(vt.id)) == 2500
    assert data.vector_exist(vt.id, 's1') and not data.vector_exist(vt.id, 'nope')
    data.delete_vectors(vt.id, ['s0', 's1'])
    assert len(data.vector_sha1s(vt.id)) == 2498
    mp = data.upsert_map(Map(id=-1, source='x', name='umap', key='sha1', count=1, data=['s1', 0.5, -1.0]))
    assert data.get_maps(id=mp.id)[0].data == ['s1', 0.5, -1.0]
    # other plugins' vector types are off limits
    conn = sqlite3.connect(str(data.base_path / 'media.db'))
    conn.execute("INSERT INTO vector_types (id, source, params) VALUES (999, 'Other', '{}')")
    conn.commit()
    conn.close()
    with pytest.raises(PermissionError):
        data.delete_vectors(999)


def test_readonly_connections(data):
    conn = data.pool.read('data')
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("DELETE FROM instances")


def test_ids_allocation(data):
    a = data.allocate_ids('maps', 3)
    b = data.allocate_ids('maps', 1)
    assert b == a + 3
    with pytest.raises(ValueError):
        data.allocate_ids('instances')
