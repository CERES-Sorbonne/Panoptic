import json
from pathlib import Path

from panoptic.core.databases.data.commit import CommitBuilder
from panoptic.core.databases.data.data_writer import DataWriter
from panoptic.core.databases.data.helper import OP_DELETE
from panoptic.core.databases.registry.registry_db import RegistryDB
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
    print(commit2.data)
    writer.apply_upsert_commit('update', commit2.data)

    rows = writer.reader.get_file_sources(id=source.id)
    assert len(rows) == 1
    assert rows[0].root_url == '/tmp/updated'

    # DELETE (Logical)
    writer.apply_delete_commit('delete', DeleteCommit(file_sources={source.id}))
    rows = writer.reader.get_file_sources(id=source.id)
    assert len(rows) == 1
    assert rows[0].operation == OP_DELETE


def test_cycle_folders():
    registry, writer = _setup()

    # INSERT
    commit1 = CommitBuilder(registry)
    source = commit1.create_file_source('filesystem', 'local', root_url='/tmp')
    folder = commit1.create_folder(source_id=source.id, path='/tmp/photos', name='photos', parent=None)
    writer.apply_upsert_commit('insert', commit1.data)

    rows = writer.reader.get_folders(id=folder.id)
    assert len(rows) == 1
    assert rows[0].name == 'photos'

    # UPDATE
    commit2 = CommitBuilder(registry)
    folder.name = 'renamed'
    commit2.update_folder(folder)
    writer.apply_upsert_commit('update', commit2.data)

    rows = writer.reader.get_folders(id=folder.id)
    assert len(rows) == 1
    assert rows[0].name == 'renamed'

    # DELETE (Logical)
    writer.apply_delete_commit('delete', DeleteCommit(folders={folder.id}))
    rows = writer.reader.get_folders(id=folder.id)
    assert len(rows) == 1
    assert rows[0].operation == OP_DELETE


def test_cycle_files():
    registry, writer = _setup()

    # INSERT
    commit1 = CommitBuilder(registry)
    source = commit1.create_file_source('filesystem', 'local', root_url='/tmp')
    folder = commit1.create_folder(source_id=source.id, path='/tmp/photos', name='photos', parent=None)
    file = commit1.create_file(name='img.jpg', folder_id=folder.id, sha1='abc123')
    writer.apply_upsert_commit('insert', commit1.data)

    rows = writer.reader.get_files(id=file.id)
    assert len(rows) == 1
    assert rows[0].name == 'img.jpg'

    # UPDATE
    commit2 = CommitBuilder(registry)
    file.name = 'img_renamed.jpg'
    commit2.update_file(file)
    writer.apply_upsert_commit('update', commit2.data)

    rows = writer.reader.get_files(id=file.id)
    assert len(rows) == 1
    assert rows[0].name == 'img_renamed.jpg'

    # DELETE (Logical)
    writer.apply_delete_commit('delete', DeleteCommit(files={file.id}))
    rows = writer.reader.get_files(id=file.id)
    assert len(rows) == 1
    assert rows[0].operation == OP_DELETE


def test_cycle_instances():
    registry, writer = _setup()

    # INSERT
    commit1 = CommitBuilder(registry)
    source = commit1.create_file_source('filesystem', 'local', root_url='/tmp')
    folder = commit1.create_folder(source_id=source.id, path='/tmp', name='tmp', parent=None)
    file = commit1.create_file(name='img.jpg', folder_id=folder.id, sha1='abc123')
    instance = commit1.create_instance(file_id=file.id, sha1='abc123')
    writer.apply_upsert_commit('insert', commit1.data)

    rows = writer.reader.get_instances(id=instance.id)
    assert len(rows) == 1
    assert rows[0].sha1 == 'abc123'

    # UPDATE
    commit2 = CommitBuilder(registry)
    instance.sha1 = 'def456'
    commit2.update_instance(instance)
    writer.apply_upsert_commit('update', commit2.data)

    rows = writer.reader.get_instances(id=instance.id)
    assert len(rows) == 1
    assert rows[0].sha1 == 'def456'

    # DELETE (Logical)
    writer.apply_delete_commit('delete', DeleteCommit(instances={instance.id}))
    rows = writer.reader.get_instances(id=instance.id)
    assert len(rows) == 1
    assert rows[0].operation == OP_DELETE


def test_cycle_properties():
    registry, writer = _setup()

    # INSERT
    commit1 = CommitBuilder(registry)
    prop = commit1.create_property(dtype='tags', mode='sha1', name='color')
    writer.apply_upsert_commit('insert', commit1.data)

    rows = writer.reader.get_properties(id=prop.id)
    assert len(rows) == 1
    assert rows[0].name == 'color'

    # UPDATE
    commit2 = CommitBuilder(registry)
    prop.name = 'color_renamed'
    commit2.update_property(prop)
    writer.apply_upsert_commit('update', commit2.data)

    rows = writer.reader.get_properties(id=prop.id)
    assert len(rows) == 1
    assert rows[0].name == 'color_renamed'

    # DELETE (Logical)
    writer.apply_delete_commit('delete', DeleteCommit(properties={prop.id}))
    rows = writer.reader.get_properties(id=prop.id)
    assert len(rows) == 1
    assert rows[0].operation == OP_DELETE


def test_cycle_tags():
    registry, writer = _setup()

    # INSERT
    commit1 = CommitBuilder(registry)
    prop = commit1.create_property(dtype='tags', mode='sha1', name='genre')
    tag = commit1.create_tag(list_id=prop.id, value='Rock', color=0xFF0000, parents=[1, 2])
    writer.apply_upsert_commit('insert', commit1.data)

    rows = writer.reader.get_tags(id=tag.id)
    assert len(rows) == 1
    assert rows[0].value == 'Rock'

    # UPDATE
    commit2 = CommitBuilder(registry)
    tag.value = 'Jazz'
    tag.color = 0x00FF00
    commit2.update_tag(tag)
    writer.apply_upsert_commit('update', commit2.data)

    rows = writer.reader.get_tags(id=tag.id)
    assert len(rows) == 1
    assert rows[0].value == 'Jazz'

    # DELETE (Logical)
    writer.apply_delete_commit('delete', DeleteCommit(tags={tag.id}))
    rows = writer.reader.get_tags(id=tag.id)
    assert len(rows) == 1
    assert rows[0].operation == OP_DELETE


def test_cycle_instance_values():
    registry, writer = _setup()

    # INSERT
    commit1 = CommitBuilder(registry)
    prop = commit1.create_property(dtype='number', mode='id', name='score')
    source = commit1.create_file_source('filesystem', 'local', root_url='/tmp')
    folder = commit1.create_folder(source_id=source.id, path='/tmp', name='tmp', parent=None)
    file = commit1.create_file(name='img.jpg', folder_id=folder.id, sha1='abc123')
    instance = commit1.create_instance(file_id=file.id, sha1='abc123')

    write = InstanceValue(property_id=prop.id, instance_id=instance.id, value=42.0)

    commit1.add_instance_value(write)

    writer.apply_upsert_commit('test_cycle', commit1.data)

    rows = writer.reader.get_instance_values(property_id=prop.id)
    assert len(rows) == 1
    assert float(rows[0].value) == 42.0

    # UPDATE
    commit2 = CommitBuilder(registry)
    write.value = 99.0
    commit2.add_instance_value(write)
    writer.apply_upsert_commit('update', commit2.data)

    rows = writer.reader.get_instance_values(property_id=prop.id)
    assert len(rows) == 1
    assert float(rows[0].value) == 99.0

    # DELETE
    writer.apply_delete_commit('delete', DeleteCommit(properties={prop.id}))
    assert len(writer.reader.get_instance_values(property_id=prop.id)) == 1
    assert writer.reader.get_properties(id=prop.id)[0].operation == OP_DELETE


def test_cycle_sha1_values():
    registry, writer = _setup()

    # INSERT
    commit1 = CommitBuilder(registry)
    prop = commit1.create_property(dtype='number', mode='sha1', name='quality')

    # Using the Sha1Value struct directly like the InstanceValue test
    write = Sha1Value(property_id=prop.id, sha1='hash_a', value=1.0)
    commit1.add_sha1_value(write)

    writer.apply_upsert_commit('insert', commit1.data)

    rows = writer.reader.get_sha1_values(property_id=prop.id)
    assert len(rows) == 1
    assert float(rows[0].value) == 1.0
    assert rows[0].sha1 == 'hash_a'

    # UPDATE
    commit2 = CommitBuilder(registry)
    # Mutate the existing object or create a new one with same PKs
    write.value = 10.0
    commit2.add_sha1_value(write)
    writer.apply_upsert_commit('update', commit2.data)

    rows = writer.reader.get_sha1_values(property_id=prop.id)
    assert len(rows) == 1
    assert float(rows[0].value) == 10.0

    # DELETE
    # Deleting the property should leave the values in the table (logical delete of parent)
    writer.apply_delete_commit('delete', DeleteCommit(properties={prop.id}))

    # Verification matches the instance_values logic
    assert len(writer.reader.get_sha1_values(property_id=prop.id)) == 1
    assert writer.reader.get_properties(id=prop.id)[0].operation == OP_DELETE