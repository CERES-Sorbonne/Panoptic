import datetime
import json
from sqlite3 import Cursor
from typing import Any, Iterable

import msgspec

from panoptic.core.databases.data.create import (
    datastore_desc, COMMITS_SCHEMA, FILE_SOURCES_SCHEMA, FOLDERS_SCHEMA, FILES_SCHEMA,
    INSTANCES_SCHEMA, PROPERTIES_SCHEMA,
    INSTANCE_VALUES_SCHEMA, SHA1_VALUES_SCHEMA, FILE_VALUES_SCHEMA,
    INSTANCE_TAG_VALUES_SCHEMA, SHA1_TAG_VALUES_SCHEMA, GENESIS_COMMIT_ID,
)
from panoptic.core.databases.entity_schema import OP_CREATE, OP_UPDATE, OP_DELETE
from panoptic.core.databases.sqlite_db import SQLiteWriter
from panoptic.models.models import PropertyType
from panoptic.core.databases.data.models import (
    Commit, DeleteCommit, UpsertCommit, DataCommit, ChangeOp, FileSource, Property,
    PropertyGroup, Tag,
)
from panoptic.core.databases.data.resolver import (
    ENTITY_SPECS, encode_key, decode_key, diff_changes, resolve,
)

_SQLITE_MAX_VARS = 900
_TAG_DTYPES = {PropertyType.tag.value, PropertyType.multi_tags.value}


class DataWriter(SQLiteWriter):
    """Writer for the data DB under the generic-log versioning architecture.

    Logged entities (properties / groups / tags / values / tag-junctions) are journaled as
    partial-diff :class:`ChangeOp` rows in a single ``entity_log`` table and materialized into
    typed *result* tables by folding the *enabled* ops (``resolver.resolve``). Undo/redo just
    flip a commit's ``active`` bit and re-resolve the entities it touched — order-independent,
    so any commit can be toggled at any position. Structural entities are hard-deleted and
    never logged.
    """

    def __init__(self, path: str):
        super().__init__(path=path, description=datastore_desc)

    # ==================================================================
    # Logged commit  (properties / property_groups / tags / values)
    # ==================================================================

    def apply_commit(self, source: str, data: DataCommit, group_id: int = None,
                     author: str = None) -> Commit:
        """Unified create/update/delete for the logged (revertable) entities.

        Builds the minimal set of :class:`ChangeOp` diffs (expanding tag-valued writes into
        per-tag junction ops and cascading deletes), appends them to ``entity_log``, then
        re-resolves and re-materializes every touched entity.
        """
        with self.transaction() as tx:
            seq = self._exec_get_sequence(tx)
            commit_id = tx.execute(
                f"SELECT COALESCE(MAX(id), 0) FROM {COMMITS_SCHEMA.table}"
            ).fetchone()[0] + 1
            now = datetime.datetime.now()
            if group_id is None:
                group_id = commit_id

            ops = self._build_ops(tx, data, commit_id)

            # Insert the (enabled) commit row *before* materializing: resolution only counts ops
            # whose commit is active, so the row must exist for the just-written ops to fold in.
            commit = Commit(id=commit_id, group_id=group_id, source=source, timestamp=now,
                            active=1, author=author)
            COMMITS_SCHEMA.upsert(tx, commit)

            if ops:
                self._append_ops(tx, ops, seq)
                touched = {(o.entity_type, o.entity_key) for o in ops}
                for et, key in touched:
                    self._materialize(tx, et, key, seq)
            return commit

    # ------------------------------------------------------------------
    # ChangeOp construction (write path)
    # ------------------------------------------------------------------

    def _build_ops(self, tx: Cursor, data: DataCommit, commit_id: int) -> list[ChangeOp]:
        ops: dict[tuple, ChangeOp] = {}  # (entity_type, key) -> op ; later writes win

        def add(op: ChangeOp | None):
            if op is not None:
                ops[(op.entity_type, op.entity_key)] = op

        del_prop_ids: list[int] = []
        del_tag_ids: list[int] = []

        for g in data.property_groups:
            add(self._entity_op(tx, 'group', g, commit_id))
        for p in data.properties:
            if p.operation == OP_DELETE:
                del_prop_ids.append(p.id)
            add(self._entity_op(tx, 'property', p, commit_id))
        for t in data.tags:
            if t.operation == OP_DELETE:
                del_tag_ids.append(t.id)
            add(self._entity_op(tx, 'tag', t, commit_id))

        dtypes = self._dtype_map(tx, data)
        for iv in data.instance_values:
            self._value_ops(tx, 'instance_value', 'instance_tag_value',
                            ('instance_id', iv.instance_id), iv.property_id, iv.value,
                            dtypes, commit_id, add)
        for sv in data.sha1_values:
            self._value_ops(tx, 'sha1_value', 'sha1_tag_value',
                            ('sha1', sv.sha1), sv.property_id, sv.value,
                            dtypes, commit_id, add)
        for fv in data.file_values:
            # No file-tag junction table: file values are always stored as scalar cells.
            add(self._scalar_value_op('file_value', fv.property_id, ('file_id', fv.file_id),
                                      fv.value, commit_id))

        # Cascade deletes (same commit, so undo restores the whole subtree).
        for op in self._cascade_delete_ops(tx, del_prop_ids, del_tag_ids, commit_id):
            add(op)

        return list(ops.values())

    def _entity_op(self, tx: Cursor, entity_type: str, incoming: msgspec.Struct,
                   commit_id: int) -> ChangeOp | None:
        spec = ENTITY_SPECS[entity_type]
        key = encode_key(tuple(getattr(incoming, f) for f in spec.pk_fields))
        if getattr(incoming, 'operation', None) == OP_DELETE:
            return ChangeOp(entity_type, key, commit_id, OP_DELETE, None)
        current = self._alive_row(tx, spec, key)
        op = OP_CREATE if current is None else OP_UPDATE
        changes = diff_changes(spec, current, incoming)
        if op == OP_UPDATE and not changes:
            return None
        return ChangeOp(entity_type, key, commit_id, op, changes)

    def _scalar_value_op(self, entity_type: str, property_id: int, extra: tuple,
                         value: Any, commit_id: int) -> ChangeOp:
        spec = ENTITY_SPECS[entity_type]
        pk = tuple(property_id if f == 'property_id' else extra[1] for f in spec.pk_fields)
        # A value set asserts existence: model it as OP_CREATE so the last enabled set wins.
        return ChangeOp(entity_type, encode_key(pk), commit_id, OP_CREATE, {'value': value})

    def _value_ops(self, tx: Cursor, value_type: str, tag_type: str, extra: tuple,
                   property_id: int, value: Any, dtypes: dict, commit_id: int, add) -> None:
        if dtypes.get(property_id) in _TAG_DTYPES:
            self._tag_junction_ops(tx, tag_type, extra, property_id, value, commit_id, add)
        else:
            add(self._scalar_value_op(value_type, property_id, extra, value, commit_id))

    def _tag_junction_ops(self, tx: Cursor, tag_type: str, extra: tuple, property_id: int,
                          value: Any, commit_id: int, add) -> None:
        spec = ENTITY_SPECS[tag_type]
        anchor_field, anchor_val = extra
        new_tags = set(value or [])
        existing = spec.schema.get(tx, operation=OP_CREATE,
                                   **{anchor_field: anchor_val, 'property_id': property_id})
        existing_tags = {r.tag_id for r in existing}

        def key_for(tag_id: int) -> str:
            pk = tuple(anchor_val if f == anchor_field
                       else property_id if f == 'property_id' else tag_id
                       for f in spec.pk_fields)
            return encode_key(pk)

        for tag_id in existing_tags - new_tags:
            add(ChangeOp(tag_type, key_for(tag_id), commit_id, OP_DELETE, None))
        for tag_id in new_tags - existing_tags:
            add(ChangeOp(tag_type, key_for(tag_id), commit_id, OP_CREATE, None))

    def _cascade_delete_ops(self, tx: Cursor, prop_ids: list[int], tag_ids: list[int],
                            commit_id: int) -> list[ChangeOp]:
        out: list[ChangeOp] = []
        tag_ids = list(tag_ids)

        if prop_ids:
            props = PROPERTIES_SCHEMA.get_index(tx, id=prop_ids)
            tag_prop_ids = [pid for pid, p in props.items() if p.dtype in _TAG_DTYPES]
            non_tag_ids = [pid for pid, p in props.items() if p.dtype not in _TAG_DTYPES]
            list_ids = [props[pid].tag_list_id for pid in tag_prop_ids if props[pid].tag_list_id is not None]

            if non_tag_ids:
                out += self._delete_ops_for(tx, 'instance_value', property_id=non_tag_ids)
                out += self._delete_ops_for(tx, 'sha1_value', property_id=non_tag_ids)
                out += self._delete_ops_for(tx, 'file_value', property_id=non_tag_ids)
            if tag_prop_ids:
                out += self._delete_ops_for(tx, 'instance_tag_value', property_id=tag_prop_ids)
                out += self._delete_ops_for(tx, 'sha1_tag_value', property_id=tag_prop_ids)
            if list_ids:
                tag_rows = ENTITY_SPECS['tag'].schema.get(tx, list_id=list_ids)
                for t in tag_rows:
                    out.append(ChangeOp('tag', encode_key((t.id,)), commit_id, OP_DELETE, None))
                    tag_ids.append(t.id)

        if tag_ids:
            out += self._delete_ops_for(tx, 'instance_tag_value', tag_id=tag_ids)
            out += self._delete_ops_for(tx, 'sha1_tag_value', tag_id=tag_ids)

        for op in out:
            op.commit = commit_id
        return out

    def _delete_ops_for(self, tx: Cursor, entity_type: str, **filters) -> list[ChangeOp]:
        spec = ENTITY_SPECS[entity_type]
        rows = spec.schema.get(tx, **filters)  # alive rows
        return [ChangeOp(entity_type, encode_key(tuple(getattr(r, f) for f in spec.pk_fields)),
                         0, OP_DELETE, None) for r in rows]

    def _dtype_map(self, tx: Cursor, data: DataCommit) -> dict[int, str]:
        p_ids = {v.property_id for v in data.instance_values}
        p_ids |= {v.property_id for v in data.sha1_values}
        p_ids |= {v.property_id for v in data.file_values}
        result: dict[int, str] = {}
        if p_ids:
            result = {pid: p.dtype for pid, p in PROPERTIES_SCHEMA.get_index(tx, id=list(p_ids)).items()}
        for p in data.properties:  # a property created in this same commit
            if p.dtype is not None:
                result[p.id] = p.dtype
        return result

    # ------------------------------------------------------------------
    # entity_log helpers + materialization
    # ------------------------------------------------------------------

    def _append_ops(self, tx: Cursor, ops: list[ChangeOp], sequence: int) -> None:
        rows = [(o.entity_type, o.entity_key, o.commit, o.op,
                 json.dumps(o.changes) if o.changes is not None else None, sequence)
                for o in ops]
        tx.executemany(
            "INSERT OR REPLACE INTO entity_log"
            " (entity_type, entity_key, commit_id, op, changes, sequence) VALUES (?,?,?,?,?,?)",
            rows,
        )

    def _enabled_ops(self, tx: Cursor, entity_type: str, key: str,
                     up_to: int | None = None) -> list[ChangeOp]:
        # commit_id 0 is the always-enabled genesis/compaction baseline (no commits row needed).
        sql = ("SELECT el.op, el.changes, el.commit_id FROM entity_log el"
               " LEFT JOIN commits c ON c.id = el.commit_id"
               " WHERE el.entity_type = ? AND el.entity_key = ?"
               " AND (el.commit_id = 0 OR c.active = 1)")
        params: list = [entity_type, key]
        if up_to is not None:
            sql += " AND el.commit_id <= ?"
            params.append(up_to)
        sql += " ORDER BY el.commit_id"
        return [ChangeOp(entity_type, key, r[2], r[0],
                         json.loads(r[1]) if r[1] is not None else None)
                for r in tx.execute(sql, params).fetchall()]

    def _touched_by_commit(self, tx: Cursor, commit_id: int) -> list[tuple[str, str]]:
        return [(r[0], r[1]) for r in tx.execute(
            "SELECT DISTINCT entity_type, entity_key FROM entity_log WHERE commit_id = ?",
            (commit_id,),
        ).fetchall()]

    def _alive_row(self, tx: Cursor, spec, key: str):
        row = self._current_row(tx, spec, key)
        return row if (row is not None and row.operation != OP_DELETE) else None

    @staticmethod
    def _current_row(tx: Cursor, spec, key: str):
        pk = decode_key(key)
        pk_arg = [pk[0]] if len(spec.pk_fields) == 1 else [tuple(pk)]
        rows = spec.schema.get_by_pk(tx, pk_arg)
        return rows[0] if rows else None

    def _materialize(self, tx: Cursor, entity_type: str, key: str, sequence: int) -> None:
        """Re-resolve one entity from its enabled ops and upsert the result row.

        Writes a fresh ``sequence`` only when the resolved state actually changes, so the
        delta reported to clients is minimal. A resolve to ``None`` tombstones a live row.
        """
        spec = ENTITY_SPECS[entity_type]
        resolved = resolve(spec, key, self._enabled_ops(tx, entity_type, key))
        current = self._current_row(tx, spec, key)

        if resolved is None:
            if current is not None and current.operation != OP_DELETE:
                spec.schema.upsert(tx, msgspec.structs.replace(current, operation=OP_DELETE),
                                   sequence=sequence)
            return

        if current is not None and self._same_state(spec, current, resolved):
            return
        spec.schema.upsert(tx, resolved, sequence=sequence)

    @staticmethod
    def _same_state(spec, a, b) -> bool:
        if getattr(a, 'operation', None) != getattr(b, 'operation', None):
            return False
        for f in spec.data_fields:
            if getattr(a, f) != getattr(b, f):
                return False
        for f in spec.set_fields:
            if set(getattr(a, f) or []) != set(getattr(b, f) or []):
                return False
        return True

    # ==================================================================
    # Undo / redo  (non-sequential, any commit, any position)
    # ==================================================================

    def set_commit_active(self, commit_id: int, active: bool):
        """Toggle a commit's enabled bit and re-resolve only the entities it touched.

        State is a pure function of the enabled set, so this works for any commit at any
        position and for concurrent multi-user histories — only the cells the commit owned
        change; everyone else's disjoint work is untouched.
        """
        if commit_id == GENESIS_COMMIT_ID:
            return  # the folded baseline is never toggled
        with self.transaction() as tx:
            seq = self._exec_get_sequence(tx)
            tx.execute(f"UPDATE {COMMITS_SCHEMA.table} SET active = ? WHERE id = ?",
                       (1 if active else 0, commit_id))
            for et, key in self._touched_by_commit(tx, commit_id):
                self._materialize(tx, et, key, seq)
                # A tag's existence lives in the `tag` entity, but its assignments live in
                # separate junction rows under other (still-active) commits. Toggling the tag
                # doesn't touch those rows, so bump their sequence to re-ship the affected value
                # cells on the next delta — the reader then rebuilds each list filtered to alive
                # tags (undo drops the tag, redo restores it). Reversible: no ops are deleted.
                if et == 'tag':
                    tag_id = decode_key(key)[0]
                    tx.execute(f"UPDATE {INSTANCE_TAG_VALUES_SCHEMA.table} SET sequence = ? WHERE tag_id = ?",
                               (seq, tag_id))
                    tx.execute(f"UPDATE {SHA1_TAG_VALUES_SCHEMA.table} SET sequence = ? WHERE tag_id = ?",
                               (seq, tag_id))

    # ==================================================================
    # Log compaction  (bound resolution cost; drop undo history behind H)
    # ==================================================================

    def compact(self, horizon_commit_id: int) -> None:
        """Fold every commit ``0 < id <= horizon`` into the frozen genesis baseline.

        Each surviving entity's enabled ops ≤ H are folded into a single genesis CREATE op
        (full snapshot); entities that fold to dead are dropped entirely (GC). Commits behind
        the horizon are deleted and become permanently non-undoable. `H` must trail every
        user's oldest still-undoable commit.
        """
        with self.transaction() as tx:
            seq = self._exec_get_sequence(tx)
            touched = [(r[0], r[1]) for r in tx.execute(
                "SELECT DISTINCT entity_type, entity_key FROM entity_log"
                " WHERE commit_id > ? AND commit_id <= ?",
                (GENESIS_COMMIT_ID, horizon_commit_id),
            ).fetchall()]

            for et, key in touched:
                spec = ENTITY_SPECS[et]
                resolved = resolve(spec, key, self._enabled_ops(tx, et, key, up_to=horizon_commit_id))
                tx.execute(
                    "DELETE FROM entity_log WHERE entity_type = ? AND entity_key = ? AND commit_id <= ?",
                    (et, key, horizon_commit_id),
                )
                if resolved is None:
                    # Dead at the baseline: drop the genesis op and GC the result row.
                    self._delete_result_row(tx, spec, key)
                    continue
                changes = self._snapshot_changes(spec, resolved)
                tx.execute(
                    "INSERT OR REPLACE INTO entity_log"
                    " (entity_type, entity_key, commit_id, op, changes, sequence) VALUES (?,?,?,?,?,?)",
                    (et, key, GENESIS_COMMIT_ID, OP_CREATE,
                     json.dumps(changes) if changes is not None else None, seq),
                )
            tx.execute(f"DELETE FROM {COMMITS_SCHEMA.table} WHERE id > ? AND id <= ?",
                       (GENESIS_COMMIT_ID, horizon_commit_id))

    @staticmethod
    def _snapshot_changes(spec, resolved) -> dict | None:
        if spec.presence_only:
            return None
        changes: dict = {}
        for f in spec.data_fields:
            v = getattr(resolved, f)
            if v is not None:
                changes[f] = v
        for f in spec.set_fields:
            vals = getattr(resolved, f) or []
            if vals:
                changes[f] = {'add': sorted(vals), 'remove': []}
        return changes

    @staticmethod
    def _delete_result_row(tx: Cursor, spec, key: str) -> None:
        pk = decode_key(key)
        pk_arg = [pk[0]] if len(spec.pk_fields) == 1 else [tuple(pk)]
        spec.schema.delete_by_pk(tx, pk_arg)

    # ------------------------------------------------------------------
    # Backwards-compat shims (UpsertCommit / DeleteCommit)
    # ------------------------------------------------------------------

    def apply_upsert_commit(self, source: str, data: UpsertCommit, group_id: int = None,
                            author: str = None) -> Commit | None:
        if data.file_sources or data.folders or data.files or data.instances:
            self.add_structural(
                file_sources=list(data.file_sources.values()),
                folders=list(data.folders.values()),
                files=list(data.files.values()),
                instances=list(data.instances.values()),
            )
        commit = DataCommit(
            properties=list(data.properties.values()),
            property_groups=list(data.property_groups.values()),
            tags=list(data.tags.values()),
            instance_values=[v for vals in data.instance_values.values() for v in vals],
            sha1_values=[v for vals in data.sha1_values.values() for v in vals],
            file_values=[v for vals in data.file_values.values() for v in vals],
        )
        if (commit.properties or commit.property_groups or commit.tags
                or commit.instance_values or commit.sha1_values or commit.file_values):
            return self.apply_commit(source, commit, group_id=group_id, author=author)
        return None

    def apply_delete_commit(self, source: str, data: DeleteCommit, group_id: int = None,
                            author: str = None) -> Commit | None:
        if data.instances:
            self.delete_instances(list(data.instances))
        if data.files:
            self.delete_files(list(data.files))
        if data.folders:
            self.delete_folders(list(data.folders))
        if data.file_sources:
            self.delete_file_sources(list(data.file_sources))

        commit = DataCommit(
            properties=[Property(id=i, operation=OP_DELETE) for i in data.properties],
            property_groups=[PropertyGroup(id=i, operation=OP_DELETE) for i in data.property_groups],
            tags=[Tag(id=i, operation=OP_DELETE) for i in data.tags],
        )
        if commit.properties or commit.property_groups or commit.tags:
            return self.apply_commit(source, commit, group_id=group_id, author=author)
        return None

    # ==================================================================
    # Structural write API  (file_sources / folders / files / instances)
    #   sequenced (delta-synced) but NOT logged: never undone, hard-deleted.
    # ==================================================================

    def add_structural(self, file_sources=None, folders=None, files=None, instances=None):
        with self.transaction() as tx:
            seq = self._exec_get_sequence(tx)
            if file_sources:
                FILE_SOURCES_SCHEMA.upsert(tx, file_sources, sequence=seq)
            if folders:
                FOLDERS_SCHEMA.upsert(tx, folders, sequence=seq)
            if files:
                FILES_SCHEMA.upsert(tx, files, sequence=seq)
            if instances:
                INSTANCES_SCHEMA.upsert(tx, instances, sequence=seq)

    def get_or_create_local_file_source(self, fs_id: int) -> int:
        sources = FILE_SOURCES_SCHEMA.get(self.conn, dtype='local')
        if sources:
            return sources[0].id
        self.add_structural(file_sources=[FileSource(
            id=fs_id, dtype='local', name='local_filesystem', root_url=None, metadata=None,
        )])
        return fs_id

    def delete_instances(self, instance_ids: list[int]) -> dict:
        with self.transaction() as tx:
            return self._delete_instances(tx, instance_ids)

    def delete_files(self, file_ids: list[int]) -> dict:
        with self.transaction() as tx:
            return self._delete_files(tx, file_ids)

    def delete_folders(self, folder_ids: list[int]) -> dict:
        with self.transaction() as tx:
            return self._delete_folders(tx, folder_ids)

    def delete_file_sources(self, source_ids: list[int]) -> dict:
        with self.transaction() as tx:
            if not source_ids:
                return {'orphan_sha1s': [], 'orphan_file_ids': []}
            # The default local file source is permanent: deleting it clears all its
            # folders but keeps the source row (created at project start, never removed).
            local_ids = {r[0] for r in FILE_SOURCES_SCHEMA.select(tx, ['id'], dtype='local')}
            folder_ids = [r[0] for r in FOLDERS_SCHEMA.select(tx, ['id'], source_id=source_ids)]
            result = self._delete_folders(tx, folder_ids)
            deletable = [s for s in source_ids if s not in local_ids]
            if deletable:
                FILE_SOURCES_SCHEMA.delete_by_pk(tx, deletable)
            return result

    # --- internal (tx-scoped) structural deletes ---

    def _delete_instances(self, tx: Cursor, instance_ids: list[int]) -> dict:
        if not instance_ids:
            return {'orphan_sha1s': [], 'orphan_file_ids': []}
        rows = INSTANCES_SCHEMA.select(tx, ['sha1', 'file_id'], id=instance_ids)
        cand_sha1s = {r[0] for r in rows if r[0]}
        cand_files = {r[1] for r in rows if r[1] is not None}
        self._delete_instance_values(tx, instance_ids)
        INSTANCES_SCHEMA.delete_by_pk(tx, instance_ids)
        return self._gc_orphans(tx, cand_sha1s, cand_files)

    def _delete_files(self, tx: Cursor, file_ids: list[int]) -> dict:
        if not file_ids:
            return {'orphan_sha1s': [], 'orphan_file_ids': []}
        inst_ids = [r[0] for r in INSTANCES_SCHEMA.select(tx, ['id'], file_id=file_ids)]
        result = self._delete_instances(tx, inst_ids)
        self._delete_file_values(tx, file_ids)
        FILES_SCHEMA.delete_by_pk(tx, file_ids)
        return result

    def _delete_folders(self, tx: Cursor, folder_ids: list[int]) -> dict:
        if not folder_ids:
            return {'orphan_sha1s': [], 'orphan_file_ids': []}
        all_folders = self._descendant_folders(tx, folder_ids)
        file_ids = [r[0] for r in FILES_SCHEMA.select(tx, ['id'], folder_id=all_folders)]
        result = self._delete_files(tx, file_ids)
        FOLDERS_SCHEMA.delete_by_pk(tx, all_folders)
        return result

    def _descendant_folders(self, tx: Cursor, folder_ids: list[int]) -> list[int]:
        seen = set(folder_ids)
        frontier = list(folder_ids)
        while frontier:
            children = [r[0] for r in FOLDERS_SCHEMA.select(tx, ['id'], parent=frontier)]
            frontier = [c for c in children if c not in seen]
            seen.update(frontier)
        return list(seen)

    # --- Python-driven orphan GC (result rows + their entity_log ops) ---

    def _gc_orphans(self, tx: Cursor, cand_sha1s, cand_file_ids) -> dict:
        orphan_sha1s = [s for s in cand_sha1s if not self._sha1_has_instance(tx, s)]
        orphan_files = [f for f in cand_file_ids if not self._file_has_instance(tx, f)]
        if orphan_sha1s:
            self._purge_value_rows(tx, 'sha1_value', 'sha1', orphan_sha1s)
            self._purge_value_rows(tx, 'sha1_tag_value', 'sha1', orphan_sha1s)
        if orphan_files:
            self._delete_file_values(tx, orphan_files)
            FILES_SCHEMA.delete_by_pk(tx, orphan_files)
        return {'orphan_sha1s': orphan_sha1s, 'orphan_file_ids': orphan_files}

    def _delete_instance_values(self, tx: Cursor, instance_ids: list[int]):
        self._purge_value_rows(tx, 'instance_value', 'instance_id', instance_ids)
        self._purge_value_rows(tx, 'instance_tag_value', 'instance_id', instance_ids)

    def _delete_file_values(self, tx: Cursor, file_ids: list[int]):
        self._purge_value_rows(tx, 'file_value', 'file_id', file_ids)

    def _purge_value_rows(self, tx: Cursor, entity_type: str, col: str, values: list) -> None:
        """Hard-delete value/junction result rows matching col IN values, plus their
        entity_log ops (structural GC — these are never undone)."""
        if not values:
            return
        spec = ENTITY_SPECS[entity_type]
        # Fetch matching rows (any operation) to compute their keys, then purge both tables.
        pk_cols = ', '.join(spec.pk_fields)
        keys: list[str] = []
        for i in range(0, len(values), _SQLITE_MAX_VARS):
            chunk = values[i:i + _SQLITE_MAX_VARS]
            ph = ', '.join('?' * len(chunk))
            for r in tx.execute(
                f"SELECT {pk_cols} FROM {spec.schema.table} WHERE {col} IN ({ph})", chunk
            ).fetchall():
                keys.append(encode_key(tuple(r)))
        self._delete_where_in(tx, spec.schema.table, col, values)
        self._purge_entity_log(tx, entity_type, keys)

    def _purge_entity_log(self, tx: Cursor, entity_type: str, keys: list[str]) -> None:
        for i in range(0, len(keys), _SQLITE_MAX_VARS - 1):
            chunk = keys[i:i + _SQLITE_MAX_VARS - 1]
            ph = ', '.join('?' * len(chunk))
            tx.execute(
                f"DELETE FROM entity_log WHERE entity_type = ? AND entity_key IN ({ph})",
                [entity_type, *chunk],
            )

    @staticmethod
    def _sha1_has_instance(tx: Cursor, sha1: str) -> bool:
        return tx.execute(
            f"SELECT 1 FROM {INSTANCES_SCHEMA.table} WHERE sha1 = ? LIMIT 1", (sha1,)
        ).fetchone() is not None

    @staticmethod
    def _file_has_instance(tx: Cursor, file_id: int) -> bool:
        return tx.execute(
            f"SELECT 1 FROM {INSTANCES_SCHEMA.table} WHERE file_id = ? LIMIT 1", (file_id,)
        ).fetchone() is not None

    @staticmethod
    def _delete_where_in(tx: Cursor, table: str, col: str, values: list):
        values = list(values)
        for i in range(0, len(values), _SQLITE_MAX_VARS):
            chunk = values[i:i + _SQLITE_MAX_VARS]
            ph = ", ".join(["?"] * len(chunk))
            tx.execute(f"DELETE FROM {table} WHERE {col} IN ({ph})", chunk)

    # --- SQL Statements ---

    def _exec_get_sequence(self, tx: Cursor) -> int:
        """Atomically increment and return the next sequence id (SQLite 3.35+ RETURNING)."""
        tx.execute("UPDATE sequence SET id = id + 1 RETURNING id;")
        res = tx.fetchone()
        if res is None:
            tx.execute("INSERT INTO sequence (id) VALUES (1)")
            return 1
        return res[0] - 1
