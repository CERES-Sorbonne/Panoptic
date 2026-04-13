import json
from pathlib import Path

from panoptic.core.databases.data.commit import CommitBuilder
from panoptic.core.databases.data.data_writer import DataWriter
from panoptic.core.databases.data.helper import OP_DELETE, OP_DIFF, OP_CREATE, OP_UPDATE
from panoptic.core.databases.registry.registry_db import RegistryDB
from panoptic.models import PropertyType
from panoptic.models.data import DeleteCommit, InstanceValue, Sha1Value


def _setup():
    reg_path = Path("~/tmp/registry.db").expanduser()
    db_path = Path("~/tmp/data.db").expanduser()
    reg_path.parent.mkdir(parents=True, exist_ok=True)

    if reg_path.exists(): reg_path.unlink()
    if db_path.exists(): db_path.unlink()

    registry = RegistryDB(str(reg_path))
    registry.start()
    writer = DataWriter(str(db_path))
    writer.start()
    return registry, writer


def test_cycle_file_sources():
    registry, writer = _setup()

    # INSERT
    commit1 = CommitBuilder(registry)
    source = commit1.create_file_source('filesystem', 'local', root_url='/tmp/data')
    writer.apply_upsert_commit('insert', commit1.data)

    rows = writer.reader.get_file_sources(id=source.id)
    assert len(rows) == 1
    assert rows[0].root_url == '/tmp/data'

    # UPDATE
    commit2 = CommitBuilder(registry)
    source.root_url = '/tmp/updated'
    commit2.update_file_source(source)
    writer.apply_upsert_commit('update', commit2.data)

    rows = writer.reader.get_file_sources(id=source.id)
    assert len(rows) == 1
    assert rows[0].root_url == '/tmp/updated'

    # DELETE (Logical)
    writer.apply_delete_commit('delete', DeleteCommit(file_sources={source.id}))
    rows = writer.reader.get_file_sources(id=source.id)
    assert len(rows) == 1
    assert rows[0].operation == OP_DELETE

    writer.set_commit_active(3, False)
    rows = writer.reader.get_file_sources(id=source.id)
    assert len(rows) == 1
    assert rows[0].operation == OP_CREATE

    writer.set_commit_active(2, False)
    rows = writer.reader.get_file_sources(id=source.id)
    assert len(rows) == 1
    assert rows[0].root_url == '/tmp/data'
    assert rows[0].operation == OP_CREATE


def test_cycle_folders():
    registry, writer = _setup()

    # INSERT (Commit 1)
    commit1 = CommitBuilder(registry)
    source = commit1.create_file_source('filesystem', 'local', root_url='/tmp')
    folder = commit1.create_folder(source_id=source.id, path='/tmp/photos', name='photos', parent=None)
    writer.apply_upsert_commit('insert', commit1.data)

    # UPDATE (Commit 2)
    commit2 = CommitBuilder(registry)
    folder.name = 'renamed'
    commit2.update_folder(folder)
    writer.apply_upsert_commit('update', commit2.data)

    # DELETE (Commit 3)
    writer.apply_delete_commit('delete', DeleteCommit(folders={folder.id}))

    # REVERT DELETE
    writer.set_commit_active(3, False)
    rows = writer.reader.get_folders(id=folder.id)
    assert len(rows) == 1
    assert rows[0].name == 'renamed'
    assert rows[0].operation == OP_CREATE

    # REVERT UPDATE
    writer.set_commit_active(2, False)
    rows = writer.reader.get_folders(id=folder.id)
    assert len(rows) == 1
    assert rows[0].name == 'photos'
    assert rows[0].operation == OP_CREATE


def test_cycle_files():
    registry, writer = _setup()

    # INSERT (Commit 1)
    commit1 = CommitBuilder(registry)
    source = commit1.create_file_source('filesystem', 'local', root_url='/tmp')
    folder = commit1.create_folder(source_id=source.id, path='/tmp/photos', name='photos', parent=None)
    file = commit1.create_file(name='img.jpg', folder_id=folder.id, sha1='abc123')
    writer.apply_upsert_commit('insert', commit1.data)

    # UPDATE (Commit 2)
    commit2 = CommitBuilder(registry)
    file.name = 'img_renamed.jpg'
    commit2.update_file(file)
    writer.apply_upsert_commit('update', commit2.data)

    # DELETE (Commit 3)
    writer.apply_delete_commit('delete', DeleteCommit(files={file.id}))

    # REVERT DELETE
    writer.set_commit_active(3, False)
    rows = writer.reader.get_files(id=file.id)
    assert rows[0].operation == OP_CREATE
    assert rows[0].name == 'img_renamed.jpg'

    # REVERT UPDATE
    writer.set_commit_active(2, False)
    rows = writer.reader.get_files(id=file.id)
    assert rows[0].name == 'img.jpg'


def test_cycle_instances():
    registry, writer = _setup()

    # INSERT (Commit 1)
    commit1 = CommitBuilder(registry)
    source = commit1.create_file_source('filesystem', 'local', root_url='/tmp')
    folder = commit1.create_folder(source_id=source.id, path='/tmp', name='tmp', parent=None)
    file = commit1.create_file(name='img.jpg', folder_id=folder.id, sha1='abc123')
    instance = commit1.create_instance(file_id=file.id, sha1='abc123')
    writer.apply_upsert_commit('insert', commit1.data)

    # UPDATE (Commit 2)
    commit2 = CommitBuilder(registry)
    instance.sha1 = 'def456'
    commit2.update_instance(instance)
    writer.apply_upsert_commit('update', commit2.data)

    # DELETE (Commit 3)
    writer.apply_delete_commit('delete', DeleteCommit(instances={instance.id}))

    # REVERT DELETE
    writer.set_commit_active(3, False)
    rows = writer.reader.get_instances(id=instance.id)
    assert rows[0].operation == OP_CREATE
    assert rows[0].sha1 == 'def456'

    # REVERT UPDATE
    writer.set_commit_active(2, False)
    rows = writer.reader.get_instances(id=instance.id)
    assert rows[0].sha1 == 'abc123'


def test_cycle_properties():
    registry, writer = _setup()

    # INSERT (Commit 1)
    commit1 = CommitBuilder(registry)
    prop = commit1.create_property(dtype='tags', mode='sha1', name='color')
    writer.apply_upsert_commit('insert', commit1.data)

    # UPDATE (Commit 2)
    commit2 = CommitBuilder(registry)
    prop.name = 'color_renamed'
    commit2.update_property(prop)
    writer.apply_upsert_commit('update', commit2.data)

    # DELETE (Commit 3)
    writer.apply_delete_commit('delete', DeleteCommit(properties={prop.id}))

    # REVERT DELETE
    writer.set_commit_active(3, False)
    rows = writer.reader.get_properties(id=prop.id)
    assert rows[0].operation == OP_CREATE
    assert rows[0].name == 'color_renamed'

    # REVERT UPDATE
    writer.set_commit_active(2, False)
    rows = writer.reader.get_properties(id=prop.id)
    assert rows[0].name == 'color'


def test_cycle_tags():
    registry, writer = _setup()

    # INSERT (Commit 1)
    commit1 = CommitBuilder(registry)
    prop = commit1.create_property(dtype='tags', mode='sha1', name='genre')
    tag = commit1.create_tag(list_id=prop.id, value='Rock', color=0xFF0000, parents=[1, 2])
    writer.apply_upsert_commit('insert', commit1.data)

    # UPDATE (Commit 2)
    commit2 = CommitBuilder(registry)
    tag.value = 'Jazz'
    commit2.update_tag(tag)
    writer.apply_upsert_commit('update', commit2.data)

    # DELETE (Commit 3)
    writer.apply_delete_commit('delete', DeleteCommit(tags={tag.id}))

    # REVERT DELETE
    writer.set_commit_active(3, False)
    rows = writer.reader.get_tags(id=tag.id)
    assert rows[0].operation == OP_CREATE
    assert rows[0].value == 'Jazz'

    # REVERT UPDATE
    writer.set_commit_active(2, False)
    rows = writer.reader.get_tags(id=tag.id)
    assert rows[0].value == 'Rock'


def test_cycle_instance_values():
    registry, writer = _setup()

    # INSERT (Commit 1)
    commit1 = CommitBuilder(registry)
    prop = commit1.create_property(dtype='number', mode='id', name='score')
    source = commit1.create_file_source('filesystem', 'local', root_url='/tmp')
    folder = commit1.create_folder(source_id=source.id, path='/tmp', name='tmp', parent=None)
    file = commit1.create_file(name='img.jpg', folder_id=folder.id, sha1='abc123')
    instance = commit1.create_instance(file_id=file.id, sha1='abc123')
    write = InstanceValue(property_id=prop.id, instance_id=instance.id, value=42.0)
    commit1.update_instance_value(write)
    writer.apply_upsert_commit('test_cycle', commit1.data)

    # UPDATE (Commit 2)
    commit2 = CommitBuilder(registry)
    write.value = 99.0
    commit2.update_instance_value(write)
    writer.apply_upsert_commit('update', commit2.data)

    # DELETE Property (Commit 3)
    writer.apply_delete_commit('delete', DeleteCommit(properties={prop.id}))

    # REVERT DELETE
    writer.set_commit_active(3, False)
    assert writer.reader.get_properties(id=prop.id)[0].operation == OP_CREATE
    assert float(writer.reader.get_instance_values(property_id=prop.id)[0].value) == 99.0

    # REVERT UPDATE
    writer.set_commit_active(2, False)
    assert float(writer.reader.get_instance_values(property_id=prop.id)[0].value) == 42.0


def test_instances_values_tags():
    registry, writer = _setup()

    # INSERT (Commit 1)
    commit1 = CommitBuilder(registry)
    prop = commit1.create_property(dtype=PropertyType.multi_tags.value, mode='id', name='score')
    source = commit1.create_file_source('filesystem', 'local', root_url='/tmp')
    folder = commit1.create_folder(source_id=source.id, path='/tmp', name='tmp', parent=None)
    file = commit1.create_file(name='img.jpg', folder_id=folder.id, sha1='abc123')
    instance = commit1.create_instance(file_id=file.id, sha1='abc123')
    write = InstanceValue(property_id=prop.id, instance_id=instance.id, value=[1, 2, 3])
    commit1.update_instance_value(write)
    writer.apply_upsert_commit('insert', commit1.data)

    # DIFF (Commit 2): [2, 3, 4]
    commit2 = CommitBuilder(registry)
    write.value = [-1, 4]
    write.operation = OP_DIFF
    commit2.update_instance_value(write)
    writer.apply_upsert_commit('diff', commit2.data)

    # UPDATE (Commit 3): [1, 4]
    commit3 = CommitBuilder(registry)
    write.value = [1, 4]
    write.operation = OP_UPDATE
    commit3.update_instance_value(write)
    writer.apply_upsert_commit('update', commit3.data)

    # DELETE PROPERTY (Commit 4)
    writer.apply_delete_commit('delete', DeleteCommit(properties={prop.id}))

    # REVERT DELETE
    writer.set_commit_active(4, False)
    assert writer.reader.get_properties(id=prop.id)[0].operation == OP_CREATE

    # REVERT FULL UPDATE -> Should go back to the Diff state [2, 3, 4]
    writer.set_commit_active(1, False)
    writer.set_commit_active(3, False)
    rows = writer.reader.get_instance_values(property_id=prop.id)
    assert rows[0].value == [4]


def test_sha1_values_tags():
    registry, writer = _setup()

    # INSERT (Commit 1)
    commit1 = CommitBuilder(registry)
    prop = commit1.create_property(dtype=PropertyType.multi_tags.value, mode='sha1', name='tags')

    # Initial state: [1, 2, 3]
    write = Sha1Value(property_id=prop.id, sha1='hash_abc', value=[1, 2, 3])
    commit1.update_sha1_value(write)
    writer.apply_upsert_commit('insert', commit1.data)

    # DIFF (Commit 2)
    # Applying [-1, 4] -> Should result in [2, 3, 4]
    commit2 = CommitBuilder(registry)
    write.value = [-1, 4]
    write.operation = OP_DIFF
    commit2.update_sha1_value(write)
    writer.apply_upsert_commit('diff', commit2.data)

    # FULL UPDATE (Commit 3)
    # Overwriting with [1, 4]
    commit3 = CommitBuilder(registry)
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
    assert writer.reader.get_properties(id=prop.id)[0].operation == OP_CREATE
    # Values should still be at the last known state [1, 4]
    rows = writer.reader.get_sha1_values(property_id=prop.id)
    assert rows[0].value == [1, 4]

    writer.set_commit_active(1, False)
    writer.set_commit_active(3, False)
    rows = writer.reader.get_sha1_values(property_id=prop.id)
    assert rows[0].value == [4]