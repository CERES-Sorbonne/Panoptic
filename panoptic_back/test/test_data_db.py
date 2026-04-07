from pathlib import Path

from panoptic.core.databases.data.commit import CommitBuilder
from panoptic.core.databases.data.data_writer import DataWriter
from panoptic.core.databases.registry.registry_db import RegistryDB
from panoptic.models.data import DeleteCommit


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
            "SELECT sha1, value FROM sha1_values_history WHERE property_id = ? AND commit_id = 2",
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