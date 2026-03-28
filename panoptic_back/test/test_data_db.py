import pytest
from datetime import datetime
from pathlib import Path

from panoptic.core.databases.data.commit import CommitBuilder
from panoptic.core.databases.data.data_writer import DataWriter
from panoptic.core.databases.registry.registry_db import RegistryDB
from panoptic.models.data import File, UpsertCommit


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
    prop = commit1.add_property(dtype="multi_tags", mode="manual", name="quality_score")

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

    # New values for the SAME 10 SHA1 hashes
    new_values = {}
    for i in range(10):
        sha1_hash = f"hash_{i}"
        val = i + 500.0  # Completely different values
        new_values[sha1_hash] = val

    commit2.add_sha1_values(prop.id, new_values)
    writer.apply_upsert_commit('override_script', commit2.data)

    # --- PHASE 3: Final Verification ---
    updated_db_values = writer.reader.get_sha1_values(property_id=prop.id)
    assert len(updated_db_values) == 10

    for row in updated_db_values:
        expected_val = float(row.sha1.split('_')[1]) + 500.0
        assert row.value == expected_val
        # Ensure the commit_id was updated to 2
        assert row.commit_id == 2

    # Verify History (Optional but recommended)
    # Check if the history table captured the previous values (0.0, 10.0, etc.)
    with writer.transaction() as tx:
        cursor = tx.execute("SELECT value FROM sha1_values_history WHERE property_id = ?", (prop.id,))
        history_rows = cursor.fetchall()
        # Should have 10 history entries from the override operation
        assert len(history_rows) == 10