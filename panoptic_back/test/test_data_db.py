"""Data-layer tests for the structural / logged split.

Structural entities (file_sources / folders / files / instances) are *sequenced* but not
*logged*: created via the structural API, hard-deleted, never undone. Editable entities
(properties / property_groups / tags / values) go through the unified ``apply_commit`` and
remain revertable via ``set_commit_active``.
"""
from pathlib import Path

from panoptic.core.databases.data.data_reader import DataReader
from panoptic.core.databases.data.data_writer import DataWriter
from panoptic.core.databases.entity_schema import OP_CREATE, OP_UPDATE, OP_DELETE
from panoptic.core.databases.data.models import (
    FileSource, Folder, File, Instance,
    DataCommit, Property, Tag, InstanceValue, Sha1Value,
)
from panoptic.models.models import PropertyType


def _setup(name: str):
    data_path = Path(f"~/tmp/{name}.db").expanduser()
    data_path.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ('', '-wal', '-shm'):
        p = Path(str(data_path) + suffix)
        if p.exists():
            p.unlink()
    writer = DataWriter(str(data_path)); writer.start()
    reader = DataReader(str(data_path)); reader.start()
    return writer, reader


def _prop(pid, dtype='text', mode='id', name='p'):
    return Property(id=pid, dtype=dtype, mode=mode, name=name, access='write',
                    tag_list_id=pid, operation=OP_CREATE)


def _prop_upd(pid, dtype='text', mode='id', name='p'):
    return Property(id=pid, dtype=dtype, mode=mode, name=name, access='write',
                    tag_list_id=pid, operation=OP_UPDATE)


# ---------------------------------------------------------------------------
# Structural entities: created + hard-deleted, NOT logged
# ---------------------------------------------------------------------------

def test_structural_tables_are_not_logged():
    from panoptic.core.databases.data.create import (
        INSTANCES_SCHEMA, FILES_SCHEMA, FOLDERS_SCHEMA, FILE_SOURCES_SCHEMA,
        PROPERTIES_SCHEMA, TAGS_SCHEMA,
    )
    for s in (INSTANCES_SCHEMA, FILES_SCHEMA, FOLDERS_SCHEMA, FILE_SOURCES_SCHEMA):
        assert s.sequenced and not s.trackable
    for s in (PROPERTIES_SCHEMA, TAGS_SCHEMA):
        assert s.sequenced and s.trackable


def test_structural_add_update_delete():
    writer, reader = _setup('data_struct')

    writer.add_structural(
        file_sources=[FileSource(id=1, dtype='filesystem', name='local', root_url='/tmp')],
        folders=[Folder(id=1, source_id=1, path='/tmp', name='tmp', parent=None)],
        files=[File(id=1, name='img.jpg', folder_id=1, sha1='abc')],
        instances=[Instance(id=1, file_id=1, sha1='abc')],
    )
    assert reader.get_instances(id=1)[0].sha1 == 'abc'
    assert reader.get_files(id=1)[0].name == 'img.jpg'

    # "Update" is a plain re-add (no operation column on structural rows).
    writer.add_structural(files=[File(id=1, name='renamed.jpg', folder_id=1, sha1='abc')])
    assert reader.get_files(id=1)[0].name == 'renamed.jpg'

    # Hard delete: the row is gone (no soft-delete tombstone).
    writer.delete_instances([1])
    assert reader.get_instances(id=1) == []


def test_delete_instance_cascades_values_and_gcs_sha1():
    writer, reader = _setup('data_gc')

    # Two instances share sha1 'A'; one has its own 'B'.
    writer.add_structural(
        files=[File(id=1, name='a', folder_id=1, sha1='A'),
               File(id=2, name='b', folder_id=1, sha1='B')],
        instances=[Instance(id=1, file_id=1, sha1='A'),
                   Instance(id=2, file_id=2, sha1='B'),
                   Instance(id=3, file_id=1, sha1='A')],
    )
    writer.apply_commit('t', DataCommit(
        properties=[_prop(10)],
        instance_values=[InstanceValue(property_id=10, instance_id=1, value='v1', operation=OP_UPDATE),
                         InstanceValue(property_id=10, instance_id=3, value='v3', operation=OP_UPDATE)],
        sha1_values=[Sha1Value(property_id=10, sha1='A', value='shaA', operation=OP_UPDATE)],
    ))

    # Delete instance 1: its instance_value goes; sha1 'A' kept (instance 3 still shares it).
    res = writer.delete_instances([1])
    assert res['orphan_sha1s'] == []
    iv = {v.instance_id for v in reader.get_instance_values(property_id=10)}
    assert iv == {3}
    assert reader.get_sha1_values(property_id=10)  # 'A' still present

    # Delete instance 3 (last holder of 'A'): sha1 'A' + file 1 are GC'd.
    res = writer.delete_instances([3])
    assert res['orphan_sha1s'] == ['A']
    assert res['orphan_file_ids'] == [1]
    assert reader.get_sha1_values(property_id=10) == []
    assert {f.id for f in reader.get_files()} == {2}


def test_delete_folder_cascades_subtree():
    writer, reader = _setup('data_folder')
    writer.add_structural(
        folders=[Folder(id=1, source_id=1, path='/root', name='root', parent=None),
                 Folder(id=2, source_id=1, path='/root/sub', name='sub', parent=1)],
        files=[File(id=1, name='a', folder_id=1, sha1='A'),
               File(id=2, name='b', folder_id=2, sha1='B')],
        instances=[Instance(id=1, file_id=1, sha1='A'),
                   Instance(id=2, file_id=2, sha1='B')],
    )
    writer.delete_folders([1])  # recurses into sub-folder 2
    assert reader.get_folders() == []
    assert reader.get_files() == []
    assert reader.get_instances() == []


# ---------------------------------------------------------------------------
# Logged entities: unified create / update / delete + undo / redo
# ---------------------------------------------------------------------------

def test_property_cycle_with_undo():
    writer, reader = _setup('data_prop')

    c1 = writer.apply_commit('t', DataCommit(properties=[_prop(10, name='color')]))
    c2 = writer.apply_commit('t', DataCommit(
        properties=[Property(id=10, dtype='text', mode='id', name='color_renamed',
                             access='write', tag_list_id=10, operation=OP_UPDATE)]))
    assert reader.get_properties(id=10)[0].name == 'color_renamed'

    # Undo the rename.
    writer.set_commit_active(c2.id, False)
    assert reader.get_properties(id=10)[0].name == 'color'
    # Redo.
    writer.set_commit_active(c2.id, True)
    assert reader.get_properties(id=10)[0].name == 'color_renamed'

    # Delete the property (operation=OP_DELETE in the unified commit) then undo the delete.
    c3 = writer.apply_commit('t', DataCommit(properties=[Property(id=10, operation=OP_DELETE)]))
    assert reader.get_properties(id=10) == []
    writer.set_commit_active(c3.id, False)
    assert reader.get_properties(id=10)[0].name == 'color_renamed'


def test_value_cycle_with_undo_and_property_delete_cascade():
    writer, reader = _setup('data_values')
    writer.add_structural(instances=[Instance(id=1, file_id=1, sha1='A')])

    writer.apply_commit('t', DataCommit(
        properties=[_prop(10, dtype='number')],
        instance_values=[InstanceValue(property_id=10, instance_id=1, value=42.0, operation=OP_UPDATE)],
    ))
    c2 = writer.apply_commit('t', DataCommit(
        instance_values=[InstanceValue(property_id=10, instance_id=1, value=99.0, operation=OP_UPDATE)]))
    assert float(reader.get_instance_values(property_id=10)[0].value) == 99.0

    writer.set_commit_active(c2.id, False)
    assert float(reader.get_instance_values(property_id=10)[0].value) == 42.0
    writer.set_commit_active(c2.id, True)

    # Deleting the property cascades to its values (logged cascade).
    writer.apply_commit('t', DataCommit(properties=[Property(id=10, operation=OP_DELETE)]))
    assert reader.get_instance_values(property_id=10) == []


# ---------------------------------------------------------------------------
# Tag junction counts
# ---------------------------------------------------------------------------

def test_instance_tag_counts():
    writer, reader = _setup('data_itags')
    writer.add_structural(instances=[Instance(id=1, file_id=1, sha1='a'),
                                     Instance(id=2, file_id=2, sha1='b')])
    writer.apply_commit('t', DataCommit(
        properties=[_prop(10, dtype=PropertyType.multi_tags.value)],
        instance_values=[
            InstanceValue(property_id=10, instance_id=1, value=[1, 2], operation=OP_UPDATE),
            InstanceValue(property_id=10, instance_id=2, value=[2, 3], operation=OP_UPDATE),
        ],
    ))
    counts = {r['tag_id']: r for r in reader.get_tag_counts()}
    assert counts[1]['instance_count'] == 1
    assert counts[2]['instance_count'] == 2
    assert counts[3]['instance_count'] == 1

    # Drop tag 1 from inst1.
    writer.apply_commit('t', DataCommit(
        instance_values=[InstanceValue(property_id=10, instance_id=1, value=[2], operation=OP_UPDATE)]))
    counts = {r['tag_id']: r for r in reader.get_tag_counts()}
    assert 1 not in counts
    assert counts[2]['instance_count'] == 2


def test_sha1_tag_counts():
    writer, reader = _setup('data_stags')
    writer.apply_commit('t', DataCommit(
        properties=[_prop(10, dtype=PropertyType.multi_tags.value, mode='sha1')],
        sha1_values=[
            Sha1Value(property_id=10, sha1='x', value=[10, 20], operation=OP_UPDATE),
            Sha1Value(property_id=10, sha1='y', value=[20, 30], operation=OP_UPDATE),
        ],
    ))
    counts = {r['tag_id']: r for r in reader.get_tag_counts()}
    assert counts[10]['sha1_count'] == 1
    assert counts[20]['sha1_count'] == 2
    assert counts[30]['sha1_count'] == 1


# ---------------------------------------------------------------------------
# Generic-log architecture: causal existence, non-sequential & multi-user undo,
# per-field collateral, compaction.  (notes/versioning_architecture.md)
# ---------------------------------------------------------------------------

from panoptic.core.databases.data.models import Tag


def test_undo_creation_removes_entity_despite_later_update():
    """Disabling the CREATE while a later UPDATE stays enabled must DELETE the entity — not
    leave a stale row (old bug P1) nor resurrect it via the UPDATE (old bug P2)."""
    writer, reader = _setup('data_reset')
    c1 = writer.apply_commit('t', DataCommit(properties=[_prop(10, name='color')]))
    writer.apply_commit('t', DataCommit(properties=[_prop_upd(10, name='renamed')]))
    assert reader.get_properties(id=10)[0].name == 'renamed'

    writer.set_commit_active(c1.id, False)          # undo the creation, keep the rename
    assert reader.get_properties(id=10) == []       # gone, not stale/resurrected

    writer.set_commit_active(c1.id, True)           # redo the creation
    assert reader.get_properties(id=10)[0].name == 'renamed'


def test_nonsequential_value_undo():
    """Toggling a commit in the *middle* of history is well-defined (state = fold of the
    enabled set), and only changes the current value when that commit was the winner."""
    writer, reader = _setup('data_nonseq')
    writer.add_structural(instances=[Instance(id=1, file_id=1, sha1='A')])
    writer.apply_commit('t', DataCommit(
        properties=[_prop(10, dtype='number')],
        instance_values=[InstanceValue(property_id=10, instance_id=1, value=1.0, operation=OP_UPDATE)]))
    c2 = writer.apply_commit('t', DataCommit(
        instance_values=[InstanceValue(property_id=10, instance_id=1, value=2.0, operation=OP_UPDATE)]))
    c3 = writer.apply_commit('t', DataCommit(
        instance_values=[InstanceValue(property_id=10, instance_id=1, value=3.0, operation=OP_UPDATE)]))

    def val():
        return float(reader.get_instance_values(property_id=10)[0].value)

    assert val() == 3.0
    writer.set_commit_active(c2.id, False)   # middle commit — c3 still wins, no visible change
    assert val() == 3.0
    writer.set_commit_active(c3.id, False)   # now c2 disabled too -> c1 wins
    assert val() == 1.0
    writer.set_commit_active(c2.id, True)    # re-enable middle -> 2.0
    assert val() == 2.0


def test_per_field_collateral_minimal():
    """Editing different fields of one entity in different commits is disjoint: undoing one
    reverts only its field, leaving the other user's field intact."""
    writer, reader = _setup('data_field')
    writer.apply_commit('t', DataCommit(
        tags=[Tag(id=1, list_id=5, value='a', color=1, parents=[], operation=OP_CREATE)]))
    ca = writer.apply_commit('userA', DataCommit(
        tags=[Tag(id=1, list_id=5, value='a', color=9, parents=[], operation=OP_UPDATE)]))
    writer.apply_commit('userB', DataCommit(
        tags=[Tag(id=1, list_id=5, value='b', color=9, parents=[], operation=OP_UPDATE)]))

    t = reader.get_tags(id=1)[0]
    assert (t.color, t.value) == (9, 'b')

    writer.set_commit_active(ca.id, False)   # undo only the color change
    t = reader.get_tags(id=1)[0]
    assert (t.color, t.value) == (1, 'b')    # value 'b' (userB) preserved; color reverted


def test_parents_are_an_or_set():
    """tag.parents is a per-element OR-Set: concurrent add of different parents both survive,
    and undoing one add removes only that element."""
    writer, reader = _setup('data_parents')
    writer.apply_commit('t', DataCommit(
        tags=[Tag(id=1, list_id=5, value='x', color=0, parents=[], operation=OP_CREATE)]))
    a = writer.apply_commit('A', DataCommit(
        tags=[Tag(id=1, list_id=5, value='x', color=0, parents=[7], operation=OP_UPDATE)]))
    writer.apply_commit('B', DataCommit(
        tags=[Tag(id=1, list_id=5, value='x', color=0, parents=[7, 8], operation=OP_UPDATE)]))
    assert set(reader.get_tags(id=1)[0].parents) == {7, 8}

    writer.set_commit_active(a.id, False)    # undo add of 7; 8 (added by B) stays
    assert set(reader.get_tags(id=1)[0].parents) == {8}


def test_revert_property_creation_with_dependent_data():
    """Reverting a property CREATION while another author populated tags/values/rename:
    the property vanishes, nothing is destroyed, and redo restores everyone's work."""
    writer, reader = _setup('data_multiuser')
    writer.add_structural(instances=[Instance(id=1, file_id=1, sha1='A'),
                                     Instance(id=2, file_id=2, sha1='B')])
    c_create = writer.apply_commit('A', DataCommit(
        properties=[_prop(10, dtype=PropertyType.multi_tags.value)]))
    writer.apply_commit('B', DataCommit(
        tags=[Tag(id=1, list_id=10, value='foo', color=0, parents=[], operation=OP_CREATE)]))
    writer.apply_commit('B', DataCommit(
        instance_values=[InstanceValue(property_id=10, instance_id=1, value=[1], operation=OP_UPDATE)]))
    writer.apply_commit('B', DataCommit(
        properties=[_prop_upd(10, dtype=PropertyType.multi_tags.value, name='renamed')]))

    assert reader.get_properties(id=10)[0].name == 'renamed'
    assert {v.tag_id for v in reader.get_instance_tag_values(property_id=10)} == {1}

    # userA reverts the creation — property disappears, dependent data goes dormant.
    writer.set_commit_active(c_create.id, False)
    assert reader.get_properties(id=10) == []

    # userA redoes — property AND all of userB's concurrent work come back intact.
    writer.set_commit_active(c_create.id, True)
    assert reader.get_properties(id=10)[0].name == 'renamed'
    assert {v.tag_id for v in reader.get_instance_tag_values(property_id=10)} == {1}


def test_compaction_baseline():
    """Compaction folds the settled prefix into the frozen baseline: current state is
    preserved, old commits become non-undoable, and new commits fall back to the baseline."""
    writer, reader = _setup('data_compact')
    c1 = writer.apply_commit('t', DataCommit(properties=[_prop(10, name='a')]))
    c2 = writer.apply_commit('t', DataCommit(properties=[_prop_upd(10, name='b')]))

    writer.compact(c2.id)
    assert reader.get_properties(id=10)[0].name == 'b'
    assert reader.get_commits() == []                 # prefix commits dropped from history

    writer.set_commit_active(c1.id, False)            # behind the horizon -> no-op
    assert reader.get_properties(id=10)[0].name == 'b'

    c3 = writer.apply_commit('t', DataCommit(properties=[_prop_upd(10, name='c')]))
    assert reader.get_properties(id=10)[0].name == 'c'
    writer.set_commit_active(c3.id, False)            # undo falls back to the baseline ('b')
    assert reader.get_properties(id=10)[0].name == 'b'
