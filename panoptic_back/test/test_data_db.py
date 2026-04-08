import json
from pathlib import Path

from panoptic.core.databases.data.commit import CommitBuilder
from panoptic.core.databases.data.data_writer import DataWriter, OP_DELETE, OP_ADD, OP_SUB
from panoptic.core.databases.registry.registry_db import RegistryDB
from panoptic.models.data import DeleteCommit

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
    source = commit1.add_file_source('filesystem', 'local', root_url='/tmp/data')
    writer.apply_upsert_commit('insert', commit1.data)

    rows = writer.reader.get_file_sources(id=source.id)
    assert len(rows) == 1
    assert rows[0].root_url == '/tmp/data'

    # UPDATE
    commit2 = CommitBuilder(registry)
    updated = commit2.add_file_source('filesystem', 'local', root_url='/tmp/updated')
    updated.id = source.id
    writer.apply_upsert_commit('update', commit2.data)

    rows = writer.reader.get_file_sources(id=source.id)
    assert len(rows) == 1
    assert rows[0].root_url == '/tmp/updated'

    # DELETE
    writer.apply_delete_commit('delete', DeleteCommit(file_sources={source.id}))
    assert len(writer.reader.get_file_sources(id=source.id)) == 0


def test_cycle_folders():
    registry, writer = _setup()

    # INSERT
    commit1 = CommitBuilder(registry)
    source = commit1.add_file_source('filesystem', 'local', root_url='/tmp')
    folder = commit1.add_folder(source_id=source.id, path='/tmp/photos', name='photos', parent=None)
    writer.apply_upsert_commit('insert', commit1.data)

    rows = writer.reader.get_folders(id=folder.id)
    assert len(rows) == 1
    assert rows[0].name == 'photos'

    # UPDATE
    commit2 = CommitBuilder(registry)
    updated = commit2.add_folder(source_id=source.id, path='/tmp/photos', name='renamed', parent=None)
    updated.id = folder.id
    writer.apply_upsert_commit('update', commit2.data)

    rows = writer.reader.get_folders(id=folder.id)
    assert len(rows) == 1
    assert rows[0].name == 'renamed'

    # DELETE
    writer.apply_delete_commit('delete', DeleteCommit(folders={folder.id}))
    assert len(writer.reader.get_folders(id=folder.id)) == 0


def test_cycle_files():
    registry, writer = _setup()

    # INSERT
    commit1 = CommitBuilder(registry)
    source = commit1.add_file_source('filesystem', 'local', root_url='/tmp')
    folder = commit1.add_folder(source_id=source.id, path='/tmp/photos', name='photos', parent=None)
    file = commit1.add_file(name='img.jpg', folder_id=folder.id, sha1='abc123')
    writer.apply_upsert_commit('insert', commit1.data)

    rows = writer.reader.get_files(id=file.id)
    assert len(rows) == 1
    assert rows[0].name == 'img.jpg'
    assert rows[0].sha1 == 'abc123'

    # UPDATE
    commit2 = CommitBuilder(registry)
    updated = commit2.add_file(name='img_renamed.jpg', folder_id=folder.id, sha1='abc123')
    updated.id = file.id
    writer.apply_upsert_commit('update', commit2.data)

    rows = writer.reader.get_files(id=file.id)
    assert len(rows) == 1
    assert rows[0].name == 'img_renamed.jpg'

    # DELETE
    writer.apply_delete_commit('delete', DeleteCommit(files={file.id}))
    assert len(writer.reader.get_files(id=file.id)) == 0


def test_cycle_instances():
    registry, writer = _setup()

    # INSERT
    commit1 = CommitBuilder(registry)
    source = commit1.add_file_source('filesystem', 'local', root_url='/tmp')
    folder = commit1.add_folder(source_id=source.id, path='/tmp', name='tmp', parent=None)
    file = commit1.add_file(name='img.jpg', folder_id=folder.id, sha1='abc123')
    instance = commit1.add_instance(file_id=file.id, sha1='abc123')
    writer.apply_upsert_commit('insert', commit1.data)

    rows = writer.reader.get_instances(id=instance.id)
    assert len(rows) == 1
    assert rows[0].sha1 == 'abc123'

    # UPDATE
    commit2 = CommitBuilder(registry)
    updated = commit2.add_instance(file_id=file.id, sha1='def456')
    updated.id = instance.id
    writer.apply_upsert_commit('update', commit2.data)

    rows = writer.reader.get_instances(id=instance.id)
    assert len(rows) == 1
    assert rows[0].sha1 == 'def456'

    # DELETE
    writer.apply_delete_commit('delete', DeleteCommit(instances={instance.id}))
    assert len(writer.reader.get_instances(id=instance.id)) == 0


def test_cycle_properties():
    registry, writer = _setup()

    # INSERT
    commit1 = CommitBuilder(registry)
    prop = commit1.add_property(name='color', dtype='tags', mode='sha1')
    writer.apply_upsert_commit('insert', commit1.data)

    rows = writer.reader.get_properties(id=prop.id)
    assert len(rows) == 1
    assert rows[0].name == 'color'

    # UPDATE
    commit2 = CommitBuilder(registry)
    updated = commit2.add_property(name='color_renamed', dtype='tags', mode='sha1')
    updated.id = prop.id
    writer.apply_upsert_commit('update', commit2.data)

    rows = writer.reader.get_properties(id=prop.id)
    assert len(rows) == 1
    assert rows[0].name == 'color_renamed'

    # DELETE
    writer.apply_delete_commit('delete', DeleteCommit(properties={prop.id}))
    assert len(writer.reader.get_properties(id=prop.id)) == 0


def test_cycle_tags():
    registry, writer = _setup()

    # INSERT
    commit1 = CommitBuilder(registry)
    prop = commit1.add_property(name='genre', dtype='tags', mode='sha1')
    tag = commit1.add_tag(list_id=prop.id, value='Rock', color=0xFF0000, parents=[1, 2])
    writer.apply_upsert_commit('insert', commit1.data)

    rows = writer.reader.get_tags(id=tag.id)
    assert len(rows) == 1
    assert rows[0].value == 'Rock'
    assert rows[0].parents == [1, 2]

    # UPDATE
    commit2 = CommitBuilder(registry)
    updated = commit2.add_tag(list_id=prop.id, value='Jazz', color=0x00FF00, parents=[3])
    updated.id = tag.id
    writer.apply_upsert_commit('update', commit2.data)

    rows = writer.reader.get_tags(id=tag.id)
    assert len(rows) == 1
    assert rows[0].value == 'Jazz'
    assert rows[0].parents == [3]

    # DELETE
    writer.apply_delete_commit('delete', DeleteCommit(tags={tag.id}))
    assert len(writer.reader.get_tags(id=tag.id)) == 0


def test_cycle_instance_values():
    registry, writer = _setup()

    # INSERT
    commit1 = CommitBuilder(registry)
    prop = commit1.add_property(name='score', dtype='number', mode='id')
    source = commit1.add_file_source('filesystem', 'local', root_url='/tmp')
    folder = commit1.add_folder(source_id=source.id, path='/tmp', name='tmp', parent=None)
    file = commit1.add_file(name='img.jpg', folder_id=folder.id, sha1='abc123')
    instance = commit1.add_instance(file_id=file.id, sha1='abc123')

    values = commit1.add_instance_value_write(prop.id)
    values.keys = [instance.id]
    values.values = [42.0]
    writer.apply_upsert_commit('insert', commit1.data)

    rows = writer.reader.get_instance_values(property_id=prop.id)
    assert len(rows) == 1
    assert float(rows[0].value) == 42.0

    # UPDATE
    commit2 = CommitBuilder(registry)
    values2 = commit2.add_instance_value_write(prop.id)
    values2.keys = [instance.id]
    values2.values = [99.0]
    writer.apply_upsert_commit('update', commit2.data)

    rows = writer.reader.get_instance_values(property_id=prop.id)
    assert len(rows) == 1
    assert float(rows[0].value) == 99.0

    # DELETE
    writer.apply_delete_commit('delete', DeleteCommit(properties={prop.id}))
    assert len(writer.reader.get_instance_values(property_id=prop.id)) == 0


def test_cycle_sha1_values():
    registry, writer = _setup()

    # INSERT
    commit1 = CommitBuilder(registry)
    prop = commit1.add_property(name='quality', dtype='number', mode='sha1')

    values = commit1.add_sha1_value_write(prop.id)
    values.keys = ['hash_a', 'hash_b', 'hash_c']
    values.values = [1.0, 2.0, 3.0]
    writer.apply_upsert_commit('insert', commit1.data)

    rows = writer.reader.get_sha1_values(property_id=prop.id)
    assert len(rows) == 3
    val_map = {r.sha1: float(r.value) for r in rows}
    assert val_map == {'hash_a': 1.0, 'hash_b': 2.0, 'hash_c': 3.0}

    # UPDATE
    commit2 = CommitBuilder(registry)
    values2 = commit2.add_sha1_value_write(prop.id)
    values2.keys = ['hash_a', 'hash_b', 'hash_c']
    values2.values = [10.0, 20.0, 30.0]
    writer.apply_upsert_commit('update', commit2.data)

    rows = writer.reader.get_sha1_values(property_id=prop.id)
    assert len(rows) == 3
    val_map = {r.sha1: float(r.value) for r in rows}
    assert val_map == {'hash_a': 10.0, 'hash_b': 20.0, 'hash_c': 30.0}

    # DELETE
    writer.apply_delete_commit('delete', DeleteCommit(properties={prop.id}))
    assert len(writer.reader.get_sha1_values(property_id=prop.id)) == 0


def test_writer_history_logic():
    # 1. Setup paths
    reg_path = Path("~/tmp/registry.db").expanduser()
    db_path = Path("~/tmp/data.db").expanduser()

    reg_path.parent.mkdir(parents=True, exist_ok=True)

    if reg_path.exists(): reg_path.unlink()
    if db_path.exists(): db_path.unlink()

    # Initialize Dependencies
    registry = RegistryDB(str(reg_path))
    registry.start()

    # Instantiate Writer
    writer = DataWriter(str(db_path))
    writer.start()

    commit = CommitBuilder(registry)
    new_source = commit.add_file_source('filesystem', 'local', root_url='/Users/david/tmp')

    writer.apply_upsert_commit('script', commit.data)

    db_sources = writer.reader.get_file_sources(id=new_source.id)
    assert(len(db_sources) == 1)
    assert(db_sources[0].id == new_source.id)


def test_writer_sha1_values_override():
    # 1. Setup paths
    reg_path = Path("~/tmp/registry.db").expanduser()
    db_path = Path("~/tmp/data.db").expanduser()
    reg_path.parent.mkdir(parents=True, exist_ok=True)

    if reg_path.exists(): reg_path.unlink()
    if db_path.exists(): db_path.unlink()

    # Initialize Dependencies
    registry = RegistryDB(str(reg_path))
    registry.start()

    writer = DataWriter(str(db_path))
    writer.start()

    # --- PHASE 1: Initial Insert ---
    commit1 = CommitBuilder(registry)

    # Add a property
    prop = commit1.add_property(dtype="multi_tags", mode="sha1", name="quality_score")

    # Add 10 SHA1 values for this property
    initial_values = {}
    for i in range(10):
        sha1_hash = f"hash_{i}"
        val = i * 10.0
        initial_values[sha1_hash] = val

    values = commit1.add_sha1_value_write(prop.id)
    values.keys = list(initial_values.keys())
    values.values = list(initial_values.values())
    writer.apply_upsert_commit('override_test', commit1.data)
    # Verify initial state
    db_values = writer.reader.get_sha1_values(property_id=prop.id)

    assert len(db_values) == 10
    for row in db_values:
        assert float(row.value) == float(row.sha1.split('_')[1]) * 10.0

    # --- PHASE 2: Override ---
    commit2 = CommitBuilder(registry)

    # Define new values for the same 10 hashes
    overridden_values = {}
    for i in range(10):
        sha1_hash = f"hash_{i}"
        val = i + 500.0  # New distinct value
        overridden_values[sha1_hash] = val

    # Create the write order for the same property
    ov_write = commit2.add_sha1_value_write(prop.id)
    ov_write.keys = list(overridden_values.keys())
    ov_write.values = list(overridden_values.values())

    # This should trigger the 'existing' logic in _upsert_commit_sha1_values
    writer.apply_upsert_commit('override_test', commit2.data)

    # --- PHASE 3: Verification ---
    # 1. Check current state (should be the new values)
    updated_db_values = writer.reader.get_sha1_values(property_id=prop.id)
    assert len(updated_db_values) == 10
    for row in updated_db_values:
        idx = int(row.sha1.split('_')[1])
        assert float(row.value) == idx + 500.0
        assert row.commit_id == 2

    # 2. Check history (should contain the values from Commit 1)
    # We query the history table directly via the reader or a raw transaction
    with writer.transaction() as tx:
        cursor = tx.execute(
            "SELECT sha1, value FROM sha1_values_reverts WHERE property_id = ? AND commit_id = 2",
            (prop.id,)
        )
        history_rows = cursor.fetchall()

    assert len(history_rows) == 10
    for sha1, value in history_rows:
        idx = int(sha1.split('_')[1])
        # The history stores what was there BEFORE the update
        assert float(value) == idx * 10.0

    # --- PHASE 4: Delete Property ---
    # We want to see if deleting the property also cleans up values (or handles them correctly)
    delete_req = DeleteCommit(properties={prop.id})

    # Execute the deletion
    # This should trigger _handle_properties with a None value (delete mode)
    # and ideally clear or archive associated values.
    writer.apply_delete_commit('delete_test', delete_req)

    # --- PHASE 5: Post-Deletion Verification ---

    # 1. Verify Property is gone
    db_prop = writer.reader.get_properties(id=prop.id)
    assert len(db_prop) == 0, "Property should be deleted from the properties table"

    # 2. Verify current SHA1 values are gone
    # Depending on your business logic, deleting a property should remove its current values
    remaining_values = writer.reader.get_sha1_values(property_id=prop.id)
    assert len(remaining_values) == 0, "Values associated with the deleted property should be gone"

    # 3. Verify the Commit Log (The "Undo" capability)
    last_commit = writer.reader.get_commit_by_id(3)
    assert last_commit is not None
    assert last_commit.source == "delete_test"

def test_writer_sha1_values_list_override():
    reg_path = Path("~/tmp/registry.db").expanduser()
    db_path = Path("~/tmp/data.db").expanduser()
    reg_path.parent.mkdir(parents=True, exist_ok=True)

    if reg_path.exists(): reg_path.unlink()
    if db_path.exists(): db_path.unlink()

    registry = RegistryDB(str(reg_path))
    registry.start()

    writer = DataWriter(str(db_path))
    writer.start()

    # --- PHASE 1: Initial Insert ---
    commit1 = CommitBuilder(registry)

    prop = commit1.add_property(dtype="multi_tags", mode="sha1", name="tag_lists")

    initial_values = {}
    for i in range(10):
        sha1_hash = f"hash_{i}"
        initial_values[sha1_hash] = [i, i + 1, i + 2]

    values = commit1.add_sha1_value_write(prop.id)
    values.keys = list(initial_values.keys())
    values.values = list(initial_values.values())
    writer.apply_upsert_commit('list_override_test', commit1.data)

    db_values = writer.reader.get_sha1_values(property_id=prop.id)
    assert len(db_values) == 10
    for row in db_values:
        idx = int(row.sha1.split('_')[1])
        assert json.dumps(row.value) == json.dumps([idx, idx + 1, idx + 2])

    # --- PHASE 2: Override ---
    commit2 = CommitBuilder(registry)

    overridden_values = {}
    for i in range(10):
        sha1_hash = f"hash_{i}"
        overridden_values[sha1_hash] = [i + 100, i + 200, i + 300]

    ov_write = commit2.add_sha1_value_write(prop.id)
    ov_write.keys = list(overridden_values.keys())
    ov_write.values = list(overridden_values.values())
    writer.apply_upsert_commit('list_override_test', commit2.data)

    # --- PHASE 3: Verification ---
    updated_db_values = writer.reader.get_sha1_values(property_id=prop.id)
    assert len(updated_db_values) == 10
    for row in updated_db_values:
        idx = int(row.sha1.split('_')[1])
        assert row.value == [idx + 100, idx + 200, idx + 300]
        assert row.commit_id == 2

    with writer.transaction() as tx:
        cursor = tx.execute(
            "SELECT sha1, value FROM sha1_values_reverts WHERE property_id = ? AND commit_id = 2",
            (prop.id,)
        )
        history_rows = cursor.fetchall()

    assert len(history_rows) == 10

    # --- PHASE 4: Delete Property ---
    delete_req = DeleteCommit(properties={prop.id})
    writer.apply_delete_commit('delete_test', delete_req)

    # --- PHASE 5: Post-Deletion Verification ---
    db_prop = writer.reader.get_properties(id=prop.id)
    assert len(db_prop) == 0, "Property should be deleted from the properties table"

    remaining_values = writer.reader.get_sha1_values(property_id=prop.id)
    assert len(remaining_values) == 0, "Values associated with the deleted property should be gone"

    last_commit = writer.reader.get_commit_by_id(3)
    assert last_commit is not None
    assert last_commit.source == "delete_test"

def test_writer_tags_cascade_delete():
    reg_path = Path("~/tmp/registry.db").expanduser()
    db_path = Path("~/tmp/data.db").expanduser()
    reg_path.parent.mkdir(parents=True, exist_ok=True)

    if reg_path.exists(): reg_path.unlink()
    if db_path.exists(): db_path.unlink()

    registry = RegistryDB(str(reg_path))
    registry.start()
    writer = DataWriter(str(db_path))
    writer.start()

    # --- PHASE 1: Create Property and Tags ---
    commit1 = CommitBuilder(registry)
    prop = commit1.add_property(dtype="string", mode="id", name="genre")

    # Add a parent tag
    tag_parent = commit1.add_tag(list_id=prop.id, value="Music", color=0xFF0000, parents=[1, 2, 3])
    # Add a child tag
    tag_child = commit1.add_tag(list_id=prop.id, value="Rock", color=1, parents=[tag_parent.id])

    writer.apply_upsert_commit('initial_setup', commit1.data)

    # Verify tags exist
    db_tags = writer.reader.get_tags(list_id=prop.id)
    assert len(db_tags) == 2
    assert type(db_tags[0].parents) == list
    assert len(db_tags[0].parents) == 3

    # --- PHASE 2: Delete Property (Trigger Cascade to Tags) ---
    delete_req = DeleteCommit(properties={prop.id})
    writer.apply_delete_commit('cascade_test', delete_req)



def test_writer_tag_direct_delete():
    reg_path = Path("~/tmp/registry.db").expanduser()
    db_path = Path("~/tmp/data.db").expanduser()

    registry = RegistryDB(str(reg_path))
    registry.start()
    writer = DataWriter(str(db_path))
    writer.start()

    # Setup
    commit1 = CommitBuilder(registry)
    prop = commit1.add_property(dtype='tags', mode='sha1', name="status")
    tag = commit1.add_tag(list_id=prop.id, value="Active", color=1)
    writer.apply_upsert_commit('setup', commit1.data)

    # Delete specific tag directly
    delete_req = DeleteCommit(tags={tag.id})
    writer.apply_delete_commit('tag_only_delete', delete_req)

    # Verify tag gone but property remains
    assert len(writer.reader.get_tags(id=tag.id)) == 0
    assert len(writer.reader.get_properties(id=prop.id)) == 1


def test_writer_sha1_performance():
    import time

    reg_path = Path("~/tmp/registry.db").expanduser()
    db_path = Path("~/tmp/data.db").expanduser()
    reg_path.parent.mkdir(parents=True, exist_ok=True)

    if reg_path.exists(): reg_path.unlink()
    if db_path.exists(): db_path.unlink()

    registry = RegistryDB(str(reg_path))
    registry.start()
    writer = DataWriter(str(db_path))
    writer.start()

    N = 100_000

    # --- INSERT ---
    commit1 = CommitBuilder(registry)
    prop = commit1.add_property(dtype="multi_tags", mode="sha1", name="perf_prop")

    values = commit1.add_sha1_value_write(prop.id)
    values.keys = [f"hash_{i}" for i in range(N)]
    values.values = [i * 1.0 for i in range(N)]

    t0 = time.perf_counter()
    writer.apply_upsert_commit('perf_insert', commit1.data)
    t1 = time.perf_counter()
    print(f"\nINSERT {N:,} rows: {t1 - t0:.2f}s")

    # --- QUERY ---
    t0 = time.perf_counter()
    rows = writer.reader.get_sha1_values(property_id=prop.id)
    t1 = time.perf_counter()
    print(f"QUERY  {N:,} rows: {t1 - t0:.2f}s")
    assert len(rows) == N

    # --- UPDATE ---
    commit2 = CommitBuilder(registry)
    ov_write = commit2.add_sha1_value_write(prop.id)
    ov_write.keys = [f"hash_{i}" for i in range(N)]
    ov_write.values = [i * 2.0 for i in range(N)]

    t0 = time.perf_counter()
    writer.apply_upsert_commit('perf_update', commit2.data)
    t1 = time.perf_counter()
    print(f"UPDATE {N:,} rows: {t1 - t0:.2f}s")

    # --- QUERY AFTER UPDATE ---
    t0 = time.perf_counter()
    rows = writer.reader.get_sha1_values(property_id=prop.id)
    t1 = time.perf_counter()
    print(f"QUERY  {N:,} rows (post-update): {t1 - t0:.2f}s")
    assert len(rows) == N

    return
    # --- DELETE ---
    delete_req = DeleteCommit(properties={prop.id})

    t0 = time.perf_counter()
    writer.apply_delete_commit('perf_delete', delete_req)
    t1 = time.perf_counter()
    print(f"DELETE {N:,} rows: {t1 - t0:.2f}s")

    assert len(writer.reader.get_sha1_values(property_id=prop.id)) == 0
    assert len(writer.reader.get_properties(id=prop.id)) == 0

def test_sha1_values_tag_add():
    registry, writer = _setup()

    # --- PHASE 1: Insert initial tag lists ---
    commit1 = CommitBuilder(registry)
    prop = commit1.add_property(name='tags_prop', dtype='multi_tags', mode='sha1')

    values = commit1.add_sha1_value_write(prop.id)
    values.keys = ['hash_a', 'hash_b', 'hash_c']
    values.values = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
    writer.apply_upsert_commit('insert', commit1.data)

    rows = writer.reader.get_sha1_values(property_id=prop.id)
    assert len(rows) == 3
    val_map = {r.sha1: r.value for r in rows}
    assert val_map['hash_a'] == [1, 2, 3]
    assert val_map['hash_b'] == [4, 5, 6]
    assert val_map['hash_c'] == [7, 8, 9]

    # --- PHASE 2: Add 2 tags to each value with OP_ADD ---
    commit2 = CommitBuilder(registry)
    add_write = commit2.add_sha1_value_write(prop.id)
    add_write.stamp_mode = OP_ADD
    add_write.keys = ['hash_a', 'hash_b', 'hash_c']
    add_write.values = [10, 11]
    writer.apply_upsert_commit('add_tags', commit2.data)

    rows = writer.reader.get_sha1_values(property_id=prop.id)
    assert len(rows) == 3
    val_map = {r.sha1: r.value for r in rows}
    assert val_map['hash_a'] == sorted([1, 2, 3, 10, 11])
    assert val_map['hash_b'] == sorted([4, 5, 6, 10, 11])
    assert val_map['hash_c'] == sorted([7, 8, 9, 10, 11])

    def test_sha1_values_tag_sub():
        registry, writer = _setup()

        # --- PHASE 1: Insert initial tag lists ---
        commit1 = CommitBuilder(registry)
        prop = commit1.add_property(name='tags_prop', dtype='multi_tags', mode='sha1')

        values = commit1.add_sha1_value_write(prop.id)
        values.keys = ['hash_a', 'hash_b', 'hash_c']
        values.values = [[1, 2, 3, 10, 11], [4, 5, 6, 10, 11], [7, 8, 9, 10, 11]]
        writer.apply_upsert_commit('insert', commit1.data)

        rows = writer.reader.get_sha1_values(property_id=prop.id)
        assert len(rows) == 3
        val_map = {r.sha1: r.value for r in rows}
        assert val_map['hash_a'] == [1, 2, 3, 10, 11]
        assert val_map['hash_b'] == [4, 5, 6, 10, 11]
        assert val_map['hash_c'] == [7, 8, 9, 10, 11]

        # --- PHASE 2: Remove 2 tags from each value with OP_SUB ---
        commit2 = CommitBuilder(registry)
        sub_write = commit2.add_sha1_value_write(prop.id)
        sub_write.stamp_mode = OP_SUB
        sub_write.keys = ['hash_a', 'hash_b', 'hash_c']
        sub_write.values = [10, 11]
        writer.apply_upsert_commit('sub_tags', commit2.data)

        rows = writer.reader.get_sha1_values(property_id=prop.id)
        assert len(rows) == 3
        val_map = {r.sha1: r.value for r in rows}
        assert val_map['hash_a'] == sorted([1, 2, 3])
        assert val_map['hash_b'] == sorted([4, 5, 6])
        assert val_map['hash_c'] == sorted([7, 8, 9])

    def test_instance_values_tag_add():
        registry, writer = _setup()

        # --- PHASE 1: Setup instances and insert initial tag lists ---
        commit1 = CommitBuilder(registry)
        prop = commit1.add_property(name='tags_prop', dtype='multi_tags', mode='id')
        source = commit1.add_file_source('filesystem', 'local', root_url='/tmp')
        folder = commit1.add_folder(source_id=source.id, path='/tmp', name='tmp', parent=None)
        file_a = commit1.add_file(name='a.jpg', folder_id=folder.id, sha1='sha_a')
        file_b = commit1.add_file(name='b.jpg', folder_id=folder.id, sha1='sha_b')
        file_c = commit1.add_file(name='c.jpg', folder_id=folder.id, sha1='sha_c')
        inst_a = commit1.add_instance(file_id=file_a.id, sha1='sha_a')
        inst_b = commit1.add_instance(file_id=file_b.id, sha1='sha_b')
        inst_c = commit1.add_instance(file_id=file_c.id, sha1='sha_c')

        values = commit1.add_instance_value_write(prop.id)
        values.keys = [inst_a.id, inst_b.id, inst_c.id]
        values.values = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
        writer.apply_upsert_commit('insert', commit1.data)

        rows = writer.reader.get_instance_values(property_id=prop.id)
        assert len(rows) == 3
        val_map = {r.instance_id: r.value for r in rows}
        assert val_map[inst_a.id] == [1, 2, 3]
        assert val_map[inst_b.id] == [4, 5, 6]
        assert val_map[inst_c.id] == [7, 8, 9]

        # --- PHASE 2: Add 2 tags to each value with OP_ADD ---
        commit2 = CommitBuilder(registry)
        add_write = commit2.add_instance_value_write(prop.id)
        add_write.stamp_mode = OP_ADD
        add_write.keys = [inst_a.id, inst_b.id, inst_c.id]
        add_write.values = [10, 11]
        writer.apply_upsert_commit('add_tags', commit2.data)

        rows = writer.reader.get_instance_values(property_id=prop.id)
        assert len(rows) == 3
        val_map = {r.instance_id: r.value for r in rows}
        assert val_map[inst_a.id] == sorted([1, 2, 3, 10, 11])
        assert val_map[inst_b.id] == sorted([4, 5, 6, 10, 11])
        assert val_map[inst_c.id] == sorted([7, 8, 9, 10, 11])

    def test_instance_values_tag_sub():
        registry, writer = _setup()

        # --- PHASE 1: Setup instances and insert initial tag lists ---
        commit1 = CommitBuilder(registry)
        prop = commit1.add_property(name='tags_prop', dtype='multi_tags', mode='id')
        source = commit1.add_file_source('filesystem', 'local', root_url='/tmp')
        folder = commit1.add_folder(source_id=source.id, path='/tmp', name='tmp', parent=None)
        file_a = commit1.add_file(name='a.jpg', folder_id=folder.id, sha1='sha_a')
        file_b = commit1.add_file(name='b.jpg', folder_id=folder.id, sha1='sha_b')
        file_c = commit1.add_file(name='c.jpg', folder_id=folder.id, sha1='sha_c')
        inst_a = commit1.add_instance(file_id=file_a.id, sha1='sha_a')
        inst_b = commit1.add_instance(file_id=file_b.id, sha1='sha_b')
        inst_c = commit1.add_instance(file_id=file_c.id, sha1='sha_c')

        values = commit1.add_instance_value_write(prop.id)
        values.keys = [inst_a.id, inst_b.id, inst_c.id]
        values.values = [[1, 2, 3, 10, 11], [4, 5, 6, 10, 11], [7, 8, 9, 10, 11]]
        writer.apply_upsert_commit('insert', commit1.data)

        rows = writer.reader.get_instance_values(property_id=prop.id)
        assert len(rows) == 3
        val_map = {r.instance_id: r.value for r in rows}
        assert val_map[inst_a.id] == [1, 2, 3, 10, 11]
        assert val_map[inst_b.id] == [4, 5, 6, 10, 11]
        assert val_map[inst_c.id] == [7, 8, 9, 10, 11]

        # --- PHASE 2: Remove 2 tags from each value with OP_SUB ---
        commit2 = CommitBuilder(registry)
        sub_write = commit2.add_instance_value_write(prop.id)
        sub_write.stamp_mode = OP_SUB
        sub_write.keys = [inst_a.id, inst_b.id, inst_c.id]
        sub_write.values = [10, 11]
        writer.apply_upsert_commit('sub_tags', commit2.data)

        rows = writer.reader.get_instance_values(property_id=prop.id)
        assert len(rows) == 3
        val_map = {r.instance_id: r.value for r in rows}
        assert val_map[inst_a.id] == sorted([1, 2, 3])
        assert val_map[inst_b.id] == sorted([4, 5, 6])
        assert val_map[inst_c.id] == sorted([7, 8, 9])