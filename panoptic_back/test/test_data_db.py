import json
from pathlib import Path

from panoptic.core.databases.data.commit import CommitBuilder
from panoptic.core.databases.data.data_reader import DataReader
from panoptic.core.databases.data.data_writer import DataWriter
from panoptic.core.databases.entity_schema import OP_DELETE, OP_DIFF, OP_CREATE, OP_UPDATE
from panoptic.core.databases.project.project_db import ProjectDB
from panoptic.models import PropertyType
from panoptic.models.data import DeleteCommit, InstanceValue, Sha1Value

from panoptic.core.databases.data.commit import CommitBuilder as CommitBuilder
from panoptic.core.databases.data.data_reader import DataReader as DataReader
from panoptic.core.databases.data.data_writer import DataWriter as DataWriter
from panoptic.core.databases.project.project_db import ProjectDB as ProjectDB
from panoptic.models.models import PropertyType as PropertyType
from panoptic.core.databases.data.models import InstanceValue as InstanceValue, Sha1Value as Sha1Value


def _setup():
    project_path = Path("~/tmp/project.db").expanduser()
    data_path = Path("~/tmp/data.db").expanduser()
    project_path.parent.mkdir(parents=True, exist_ok=True)

    if project_path.exists(): project_path.unlink()
    if data_path.exists(): data_path.unlink()

    project = ProjectDB(str(project_path))
    project.start()
    writer = DataWriter(str(data_path))
    writer.start()
    reader = DataReader(str(data_path))
    reader.start()
    return project, writer, reader


def test_cycle_file_sources():
    project, writer, reader = _setup()

    # INSERT
    commit1 = CommitBuilder(project)
    source = commit1.create_file_source('filesystem', 'local', root_url='/tmp/data')
    writer.apply_upsert_commit('insert', commit1.data)

    rows = reader.get_file_sources(id=source.id)
    assert len(rows) == 1
    assert rows[0].root_url == '/tmp/data'

    # UPDATE
    commit2 = CommitBuilder(project)
    source.root_url = '/tmp/updated'
    commit2.update_file_source(source)
    writer.apply_upsert_commit('update', commit2.data)

    rows = reader.get_file_sources(id=source.id)
    assert len(rows) == 1
    assert rows[0].root_url == '/tmp/updated'

    # DELETE (Logical)
    writer.apply_delete_commit('delete', DeleteCommit(file_sources={source.id}))
    rows = reader.get_file_sources(id=source.id)
    assert len(rows) == 1
    assert rows[0].operation == OP_DELETE

    writer.set_commit_active(3, False)
    rows = reader.get_file_sources(id=source.id)
    assert len(rows) == 1
    assert rows[0].operation == OP_CREATE

    writer.set_commit_active(2, False)
    rows = reader.get_file_sources(id=source.id)
    assert len(rows) == 1
    assert rows[0].root_url == '/tmp/data'
    assert rows[0].operation == OP_CREATE


def test_cycle_folders():
    project, writer, reader = _setup()

    # INSERT (Commit 1)
    commit1 = CommitBuilder(project)
    source = commit1.create_file_source('filesystem', 'local', root_url='/tmp')
    folder = commit1.create_folder(source_id=source.id, path='/tmp/photos', name='photos', parent=None)
    writer.apply_upsert_commit('insert', commit1.data)

    # UPDATE (Commit 2)
    commit2 = CommitBuilder(project)
    folder.name = 'renamed'
    commit2.update_folder(folder)
    writer.apply_upsert_commit('update', commit2.data)

    # DELETE (Commit 3)
    writer.apply_delete_commit('delete', DeleteCommit(folders={folder.id}))

    # REVERT DELETE
    writer.set_commit_active(3, False)
    rows = reader.get_folders(id=folder.id)
    assert len(rows) == 1
    assert rows[0].name == 'renamed'
    assert rows[0].operation == OP_CREATE

    # REVERT UPDATE
    writer.set_commit_active(2, False)
    rows = reader.get_folders(id=folder.id)
    assert len(rows) == 1
    assert rows[0].name == 'photos'
    assert rows[0].operation == OP_CREATE


def test_cycle_files():
    project, writer, reader = _setup()

    # INSERT (Commit 1)
    commit1 = CommitBuilder(project)
    source = commit1.create_file_source('filesystem', 'local', root_url='/tmp')
    folder = commit1.create_folder(source_id=source.id, path='/tmp/photos', name='photos', parent=None)
    file = commit1.create_file(name='img.jpg', folder_id=folder.id, sha1='abc123')
    writer.apply_upsert_commit('insert', commit1.data)

    # UPDATE (Commit 2)
    commit2 = CommitBuilder(project)
    file.name = 'img_renamed.jpg'
    commit2.update_file(file)
    writer.apply_upsert_commit('update', commit2.data)

    # DELETE (Commit 3)
    writer.apply_delete_commit('delete', DeleteCommit(files={file.id}))

    # REVERT DELETE
    writer.set_commit_active(3, False)
    rows = reader.get_files(id=file.id)
    assert rows[0].operation == OP_CREATE
    assert rows[0].name == 'img_renamed.jpg'

    # REVERT UPDATE
    writer.set_commit_active(2, False)
    rows = reader.get_files(id=file.id)
    assert rows[0].name == 'img.jpg'


def test_cycle_instances():
    project, writer, reader = _setup()

    # INSERT (Commit 1)
    commit1 = CommitBuilder(project)
    source = commit1.create_file_source('filesystem', 'local', root_url='/tmp')
    folder = commit1.create_folder(source_id=source.id, path='/tmp', name='tmp', parent=None)
    file = commit1.create_file(name='img.jpg', folder_id=folder.id, sha1='abc123')
    instance = commit1.create_instance(file_id=file.id, sha1='abc123')
    writer.apply_upsert_commit('insert', commit1.data)

    # UPDATE (Commit 2)
    commit2 = CommitBuilder(project)
    instance.sha1 = 'def456'
    commit2.update_instance(instance)
    writer.apply_upsert_commit('update', commit2.data)

    # DELETE (Commit 3)
    writer.apply_delete_commit('delete', DeleteCommit(instances={instance.id}))

    # REVERT DELETE
    writer.set_commit_active(3, False)
    rows = reader.get_instances(id=instance.id)
    assert rows[0].operation == OP_CREATE
    assert rows[0].sha1 == 'def456'

    # REVERT UPDATE
    writer.set_commit_active(2, False)
    rows = reader.get_instances(id=instance.id)
    assert rows[0].sha1 == 'abc123'


def test_cycle_properties():
    project, writer, reader = _setup()

    # INSERT (Commit 1)
    commit1 = CommitBuilder(project)
    prop = commit1.create_property(dtype='tags', mode='sha1', name='color')
    writer.apply_upsert_commit('insert', commit1.data)

    # UPDATE (Commit 2)
    commit2 = CommitBuilder(project)
    prop.name = 'color_renamed'
    commit2.update_property(prop)
    writer.apply_upsert_commit('update', commit2.data)

    # DELETE (Commit 3)
    writer.apply_delete_commit('delete', DeleteCommit(properties={prop.id}))

    # REVERT DELETE
    writer.set_commit_active(3, False)
    rows = reader.get_properties(id=prop.id)
    assert rows[0].operation == OP_CREATE
    assert rows[0].name == 'color_renamed'

    # REVERT UPDATE
    writer.set_commit_active(2, False)
    rows = reader.get_properties(id=prop.id)
    assert rows[0].name == 'color'


def test_cycle_tags():
    project, writer, reader = _setup()

    # INSERT (Commit 1)
    commit1 = CommitBuilder(project)
    prop = commit1.create_property(dtype='tags', mode='sha1', name='genre')
    tag = commit1.create_tag(list_id=prop.id, value='Rock', color=0xFF0000, parents=[1, 2])
    writer.apply_upsert_commit('insert', commit1.data)

    # UPDATE (Commit 2)
    commit2 = CommitBuilder(project)
    tag.value = 'Jazz'
    commit2.update_tag(tag)
    writer.apply_upsert_commit('update', commit2.data)

    # DELETE (Commit 3)
    writer.apply_delete_commit('delete', DeleteCommit(tags={tag.id}))

    # REVERT DELETE
    writer.set_commit_active(3, False)
    rows = reader.get_tags(id=tag.id)
    assert rows[0].operation == OP_CREATE
    assert rows[0].value == 'Jazz'

    # REVERT UPDATE
    writer.set_commit_active(2, False)
    rows = reader.get_tags(id=tag.id)
    assert rows[0].value == 'Rock'


def test_cycle_instance_values():
    project, writer, reader = _setup()

    # INSERT (Commit 1)
    commit1 = CommitBuilder(project)
    prop = commit1.create_property(dtype='number', mode='id', name='score')
    source = commit1.create_file_source('filesystem', 'local', root_url='/tmp')
    folder = commit1.create_folder(source_id=source.id, path='/tmp', name='tmp', parent=None)
    file = commit1.create_file(name='img.jpg', folder_id=folder.id, sha1='abc123')
    instance = commit1.create_instance(file_id=file.id, sha1='abc123')
    write = InstanceValue(property_id=prop.id, instance_id=instance.id, value=42.0)
    commit1.update_instance_value(write)
    writer.apply_upsert_commit('test_cycle', commit1.data)

    # UPDATE (Commit 2)
    commit2 = CommitBuilder(project)
    write.value = 99.0
    commit2.update_instance_value(write)
    writer.apply_upsert_commit('update', commit2.data)

    # DELETE Property (Commit 3)
    writer.apply_delete_commit('delete', DeleteCommit(properties={prop.id}))

    # REVERT DELETE
    writer.set_commit_active(3, False)
    assert reader.get_properties(id=prop.id)[0].operation == OP_CREATE
    assert float(reader.get_instance_values(property_id=prop.id)[0].value) == 99.0

    # REVERT UPDATE
    writer.set_commit_active(2, False)
    assert float(reader.get_instance_values(property_id=prop.id)[0].value) == 42.0


def test_instances_values_tags():
    project, writer, reader = _setup()

    # INSERT (Commit 1)
    commit1 = CommitBuilder(project)
    prop = commit1.create_property(dtype=PropertyType.multi_tags.value, mode='id', name='score')
    source = commit1.create_file_source('filesystem', 'local', root_url='/tmp')
    folder = commit1.create_folder(source_id=source.id, path='/tmp', name='tmp', parent=None)
    file = commit1.create_file(name='img.jpg', folder_id=folder.id, sha1='abc123')
    instance = commit1.create_instance(file_id=file.id, sha1='abc123')
    write = InstanceValue(property_id=prop.id, instance_id=instance.id, value=[1, 2, 3])
    commit1.update_instance_value(write)
    writer.apply_upsert_commit('insert', commit1.data)

    # DIFF (Commit 2): [2, 3, 4]
    commit2 = CommitBuilder(project)
    write.value = [-1, 4]
    write.operation = OP_DIFF
    commit2.update_instance_value(write)
    writer.apply_upsert_commit('diff', commit2.data)

    # UPDATE (Commit 3): [1, 4]
    commit3 = CommitBuilder(project)
    write.value = [1, 4]
    write.operation = OP_UPDATE
    commit3.update_instance_value(write)
    writer.apply_upsert_commit('update', commit3.data)

    # DELETE PROPERTY (Commit 4)
    writer.apply_delete_commit('delete', DeleteCommit(properties={prop.id}))

    # REVERT DELETE
    writer.set_commit_active(4, False)
    assert reader.get_properties(id=prop.id)[0].operation == OP_CREATE

    # REVERT FULL UPDATE -> Should go back to the Diff state [2, 3, 4]
    writer.set_commit_active(1, False)
    writer.set_commit_active(3, False)
    rows = reader.get_instance_values(property_id=prop.id)
    assert rows[0].value == [4]


def test_sha1_values_tags():
    project, writer, reader = _setup()

    # INSERT (Commit 1)
    commit1 = CommitBuilder(project)
    prop = commit1.create_property(dtype=PropertyType.multi_tags.value, mode='sha1', name='tags')

    # Initial state: [1, 2, 3]
    write = Sha1Value(property_id=prop.id, sha1='hash_abc', value=[1, 2, 3])
    commit1.update_sha1_value(write)
    writer.apply_upsert_commit('insert', commit1.data)

    # DIFF (Commit 2)
    # Applying [-1, 4] -> Should result in [2, 3, 4]
    commit2 = CommitBuilder(project)
    write.value = [-1, 4]
    write.operation = OP_DIFF
    commit2.update_sha1_value(write)
    writer.apply_upsert_commit('diff', commit2.data)

    # FULL UPDATE (Commit 3)
    # Overwriting with [1, 4]
    commit3 = CommitBuilder(project)
    write.value = [1, 4]
    write.operation = OP_UPDATE
    commit3.update_sha1_value(write)
    writer.apply_upsert_commit('full_update', commit3.data)

    # DELETE PROPERTY (Commit 4)
    writer.apply_delete_commit('delete', DeleteCommit(properties={prop.id}))

    # --- REVERT TESTING ---

    # 1. Revert Delete (Disable Commit 4)
    writer.set_commit_active(4, False)
    # Property should no longer be marked OP_DELETE
    assert reader.get_properties(id=prop.id)[0].operation == OP_CREATE
    # Values should still be at the last known state [1, 4]
    rows = reader.get_sha1_values(property_id=prop.id)
    assert rows[0].value == [1, 4]

    writer.set_commit_active(1, False)
    writer.set_commit_active(3, False)
    rows = reader.get_sha1_values(property_id=prop.id)
    assert rows[0].value == [4]


# ---------------------------------------------------------------------------
# panoptic2 — InstanceTagValue / Sha1TagValue + get_tag_counts
# ---------------------------------------------------------------------------

def _setup2():
    project_path = Path("~/tmp/project2.db").expanduser()
    data_path = Path("~/tmp/data2.db").expanduser()
    project_path.parent.mkdir(parents=True, exist_ok=True)
    if project_path.exists(): project_path.unlink()
    if data_path.exists(): data_path.unlink()

    project = ProjectDB(str(project_path))
    project.start()
    writer = DataWriter(str(data_path))
    writer.start()
    reader = DataReader(str(data_path))
    reader.start()
    return project, writer, reader


def test_instance_tag_counts():
    project, writer, reader = _setup2()

    # Setup: one multi_tags property (mode=id), two instances, three tags
    commit1 = CommitBuilder(project)
    prop = commit1.create_property(dtype=PropertyType.multi_tags.value, mode='id', name='labels')
    source = commit1.create_file_source('filesystem', 'local', root_url='/tmp')
    folder = commit1.create_folder(source_id=source.id, path='/tmp', name='tmp', parent=None)
    file1 = commit1.create_file(name='a.jpg', folder_id=folder.id, sha1='sha_a')
    file2 = commit1.create_file(name='b.jpg', folder_id=folder.id, sha1='sha_b')
    inst1 = commit1.create_instance(file_id=file1.id, sha1='sha_a')
    inst2 = commit1.create_instance(file_id=file2.id, sha1='sha_b')
    # inst1 -> tags [1, 2],  inst2 -> tags [2, 3]
    commit1.update_instance_value(InstanceValue(property_id=prop.id, instance_id=inst1.id, value=[1, 2]))
    commit1.update_instance_value(InstanceValue(property_id=prop.id, instance_id=inst2.id, value=[2, 3]))
    writer.apply_upsert_commit('insert', commit1.data)

    counts = {r['tag_id']: r for r in reader.get_tag_counts()}
    assert counts[1]['instance_count'] == 1  # only inst1
    assert counts[2]['instance_count'] == 2  # both instances
    assert counts[3]['instance_count'] == 1  # only inst2
    assert all(r['sha1_count'] == 0 for r in counts.values())

    # Update inst1 to only [2] — tag 1 should drop to 0 and disappear
    commit2 = CommitBuilder(project)
    commit2.update_instance_value(InstanceValue(property_id=prop.id, instance_id=inst1.id, value=[2]))
    writer.apply_upsert_commit('update', commit2.data)

    counts = {r['tag_id']: r for r in reader.get_tag_counts()}
    assert 1 not in counts                   # no instances have tag 1 anymore
    assert counts[2]['instance_count'] == 2
    assert counts[3]['instance_count'] == 1

    # Filtered by property_id — same results since there's only one property
    counts_filtered = {r['tag_id']: r for r in reader.get_tag_counts(property_id=prop.id)}
    assert counts_filtered == counts


def test_sha1_tag_counts():
    project, writer, reader = _setup2()

    # Setup: one multi_tags property (mode=sha1), two sha1s, three tags
    commit1 = CommitBuilder(project)
    prop = commit1.create_property(dtype=PropertyType.multi_tags.value, mode='sha1', name='genres')
    # sha1_x -> tags [10, 20],  sha1_y -> tags [20, 30]
    commit1.update_sha1_value(Sha1Value(property_id=prop.id, sha1='sha1_x', value=[10, 20]))
    commit1.update_sha1_value(Sha1Value(property_id=prop.id, sha1='sha1_y', value=[20, 30]))
    writer.apply_upsert_commit('insert', commit1.data)

    counts = {r['tag_id']: r for r in reader.get_tag_counts()}
    assert counts[10]['sha1_count'] == 1
    assert counts[20]['sha1_count'] == 2
    assert counts[30]['sha1_count'] == 1
    assert all(r['instance_count'] == 0 for r in counts.values())

    # Overwrite sha1_x with [20] only — tag 10 should disappear
    commit2 = CommitBuilder(project)
    commit2.update_sha1_value(Sha1Value(property_id=prop.id, sha1='sha1_x', value=[20]))
    writer.apply_upsert_commit('update', commit2.data)

    counts = {r['tag_id']: r for r in reader.get_tag_counts()}
    assert 10 not in counts
    assert counts[20]['sha1_count'] == 2
    assert counts[30]['sha1_count'] == 1


def test_tag_counts_mixed():
    """Both instance and sha1 tag values for the same tag_id sum correctly."""
    project, writer, reader = _setup2()

    commit1 = CommitBuilder(project)
    prop_id = commit1.create_property(dtype=PropertyType.multi_tags.value, mode='id', name='p_id')
    prop_sha1 = commit1.create_property(dtype=PropertyType.multi_tags.value, mode='sha1', name='p_sha1')
    source = commit1.create_file_source('filesystem', 'local', root_url='/tmp')
    folder = commit1.create_folder(source_id=source.id, path='/tmp', name='tmp', parent=None)
    file = commit1.create_file(name='c.jpg', folder_id=folder.id, sha1='sha_c')
    inst = commit1.create_instance(file_id=file.id, sha1='sha_c')
    # Same tag_id=5 appears in both an instance value and a sha1 value
    commit1.update_instance_value(InstanceValue(property_id=prop_id.id, instance_id=inst.id, value=[5]))
    commit1.update_sha1_value(Sha1Value(property_id=prop_sha1.id, sha1='sha_c', value=[5]))
    writer.apply_upsert_commit('insert', commit1.data)

    counts = {r['tag_id']: r for r in reader.get_tag_counts()}
    assert counts[5]['instance_count'] == 1
    assert counts[5]['sha1_count'] == 1
