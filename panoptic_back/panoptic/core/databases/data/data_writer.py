import datetime
from sqlite3 import Cursor
from typing import Any

from panoptic.core.databases.data.create import datastore_desc, COMMITS_SCHEMA, FILE_SOURCES_SCHEMA, PROPERTIES_SCHEMA, \
    PROPERTY_GROUPS_SCHEMA, TAGS_SCHEMA, INSTANCES_SCHEMA, FILES_SCHEMA, FOLDERS_SCHEMA, INSTANCE_VALUES_SCHEMA, SHA1_VALUES_SCHEMA, \
    FILE_VALUES_SCHEMA, INSTANCE_TAG_VALUES_SCHEMA, SHA1_TAG_VALUES_SCHEMA
from msgspec.structs import replace as msgspec_replace
from panoptic.core.databases.entity_schema import EntitySchema, PropertyValueSchema, OP_CREATE, OP_UPDATE, OP_DELETE
from panoptic.core.databases.sqlite_db import SQLiteWriter
from panoptic.models.models import PropertyType
from panoptic.core.databases.data.models import (
    Commit, DeleteCommit, UpsertCommit, DataCommit, FileSource, Property, Tag, PropertyGroup,
    InstanceValue, Sha1Value, FileValue, InstanceTagValue, Sha1TagValue,
)

_SQLITE_MAX_VARS = 900

OP_STAMP_SET = "stamp_set"
OP_STAMP_DIFF = "stamp_diff"

def set_commit(objs: list[Any], commit_id: int):
    for o in objs:
        o.commit_id = commit_id


class DataWriter(SQLiteWriter):
    def __init__(self, path: str):
        super().__init__(path=path, description=datastore_desc)

    # ==================================================================
    # Logged commit  (properties / property_groups / tags / values)
    # ==================================================================

    def apply_commit(self, source: str, data: DataCommit, group_id: int = None) -> Commit:
        """Unified create/update/delete for the logged (revertable) entities."""
        with self.transaction() as tx:
            seq_number = self._exec_get_sequence(tx)
            current_max = tx.execute(f"SELECT COALESCE(MAX(id), 0) FROM {COMMITS_SCHEMA.table}").fetchone()[0]
            commit_id = current_max + 1
            now = datetime.datetime.now()
            if group_id is None:
                group_id = commit_id

            # Partition into upserts (build an UpsertCommit) and deletes (id lists).
            up = UpsertCommit()
            del_props:  list[int] = []
            del_groups: list[int] = []
            del_tags:   list[int] = []

            for p in data.properties:
                (del_props.append(p.id) if p.operation == OP_DELETE else up.properties.__setitem__(p.id, p))
            for g in data.property_groups:
                (del_groups.append(g.id) if g.operation == OP_DELETE else up.property_groups.__setitem__(g.id, g))
            for t in data.tags:
                (del_tags.append(t.id) if t.operation == OP_DELETE else up.tags.__setitem__(t.id, t))
            for iv in data.instance_values:
                up.instance_values.setdefault(iv.property_id, []).append(iv)
            for sv in data.sha1_values:
                up.sha1_values.setdefault(sv.property_id, []).append(sv)
            for fv in data.file_values:
                up.file_values.setdefault(fv.property_id, []).append(fv)

            # Deletes first: cascade while parents are still active, then soft-delete them.
            self._delete_logged(tx, commit_id, seq_number, del_props, del_groups, del_tags)

            # Upserts (logged entities + value / tag-junction tables).
            self._upsert_commit_property_groups(tx, up, commit_id, seq_number)
            self._upsert_commit_properties(tx, up, commit_id, seq_number)
            self._upsert_commit_tags(tx, up, commit_id, seq_number)
            self._upsert_commit_instance_values(tx, up, commit_id, seq_number)
            self._upsert_commit_sha1_values(tx, up, commit_id, seq_number)
            self._upsert_commit_file_values(tx, up, commit_id, seq_number)
            self._upsert_commit_instance_tag_values(tx, up, commit_id, seq_number)
            self._upsert_commit_sha1_tag_values(tx, up, commit_id, seq_number)

            commit = Commit(id=commit_id, group_id=group_id, source=source, timestamp=now, active=True)
            COMMITS_SCHEMA.upsert(tx, commit, sequence=seq_number)
            return commit

    def _delete_logged(self, tx: Cursor, commit_id: int, sequence: int,
                       prop_ids: list[int], group_ids: list[int], tag_ids: list[int]):
        if prop_ids:
            self._cascade_delete_properties(tx, DeleteCommit(properties=set(prop_ids)), commit_id, sequence)
            self._delete_function(tx, PROPERTIES_SCHEMA, commit_id, sequence, id=prop_ids)
        if tag_ids:
            self._cascade_delete_tags(tx, DeleteCommit(tags=set(tag_ids)), commit_id, sequence)
            self._delete_function(tx, TAGS_SCHEMA, commit_id, sequence, id=tag_ids)
        if group_ids:
            self._delete_function(tx, PROPERTY_GROUPS_SCHEMA, commit_id, sequence, id=group_ids)

    # ------------------------------------------------------------------
    # Backwards-compat shims (UpsertCommit / DeleteCommit)
    # ------------------------------------------------------------------

    def apply_upsert_commit(self, source: str, data: UpsertCommit, group_id: int = None) -> Commit | None:
        """Compat shim: route structural entities to the structural API, logged → apply_commit."""
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
            return self.apply_commit(source, commit, group_id=group_id)
        return None

    def apply_delete_commit(self, source: str, data: DeleteCommit, group_id: int = None) -> Commit | None:
        """Compat shim: structural deletes are hard-deleted + GC'd; logged deletes go through
        the unified commit."""
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
            return self.apply_commit(source, commit, group_id=group_id)
        return None

    # ==================================================================
    # Structural write API  (file_sources / folders / files / instances)
    #   sequenced (delta-synced) but NOT logged: never undone, hard-deleted.
    # ==================================================================

    def add_structural(self, file_sources=None, folders=None, files=None, instances=None):
        """Bulk insert/update structural entities. Bumps the sequence (for delta-sync) but
        writes no commit row and no log — these are never reverted."""
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
        commit = UpsertCommit()
        commit.file_sources[fs_id] = FileSource(
            id=fs_id, dtype='local', name='local_filesystem', root_url=None, metadata=None,
        )
        self.add_structural(file_sources=list(commit.file_sources.values()))
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
            folder_ids = [r[0] for r in FOLDERS_SCHEMA.select(tx, ['id'], source_id=source_ids)]
            result = self._delete_folders(tx, folder_ids)
            if source_ids:
                FILE_SOURCES_SCHEMA.delete_by_pk(tx, source_ids)
            return result

    # --- internal (tx-scoped) structural deletes ---

    def _delete_instances(self, tx: Cursor, instance_ids: list[int]) -> dict:
        if not instance_ids:
            return {'orphan_sha1s': [], 'orphan_file_ids': []}
        # Capture candidate shared keys BEFORE the instances disappear.
        rows = INSTANCES_SCHEMA.select(tx, ['sha1', 'file_id'], id=instance_ids)
        cand_sha1s = {r[0] for r in rows if r[0]}
        cand_files = {r[1] for r in rows if r[1] is not None}
        # Per-instance value rows (current + log).  (Phase 4 turns this into FK cascade.)
        self._delete_instance_values(tx, instance_ids)
        # Hard-delete the instances themselves.
        INSTANCES_SCHEMA.delete_by_pk(tx, instance_ids)
        # GC the shared (sha1-/file-keyed) rows that just lost their last instance.
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

    # --- Python-driven orphan GC ---

    def _gc_orphans(self, tx: Cursor, cand_sha1s, cand_file_ids) -> dict:
        orphan_sha1s = [s for s in cand_sha1s if not self._sha1_has_instance(tx, s)]
        orphan_files = [f for f in cand_file_ids if not self._file_has_instance(tx, f)]
        if orphan_sha1s:
            for table in (SHA1_VALUES_SCHEMA.table, SHA1_TAG_VALUES_SCHEMA.table):
                self._delete_where_in(tx, table, 'sha1', orphan_sha1s)
                self._delete_where_in(tx, f'{table}_log', 'sha1', orphan_sha1s)
        if orphan_files:
            self._delete_file_values(tx, orphan_files)
            FILES_SCHEMA.delete_by_pk(tx, orphan_files)
        return {'orphan_sha1s': orphan_sha1s, 'orphan_file_ids': orphan_files}

    def _delete_instance_values(self, tx: Cursor, instance_ids: list[int]):
        for table in (INSTANCE_VALUES_SCHEMA.table, INSTANCE_TAG_VALUES_SCHEMA.table):
            self._delete_where_in(tx, table, 'instance_id', instance_ids)
            self._delete_where_in(tx, f'{table}_log', 'instance_id', instance_ids)

    def _delete_file_values(self, tx: Cursor, file_ids: list[int]):
        self._delete_where_in(tx, FILE_VALUES_SCHEMA.table, 'file_id', file_ids)
        self._delete_where_in(tx, f'{FILE_VALUES_SCHEMA.table}_log', 'file_id', file_ids)

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

    def set_commit_active(self, commit_id: int, active: bool):
        with self.transaction() as tx:
            sequence = self._exec_get_sequence(tx)
            commit = COMMITS_SCHEMA.get(tx, id=commit_id)[0]
            commit.active = 1 if active else 0
            COMMITS_SCHEMA.upsert(tx, commit)

            commits = COMMITS_SCHEMA.get(tx)
            disabled = {c.id for c in commits if not c.active}

            def re_compute(shema: EntitySchema):
                logs = shema.get_log(tx, commit_id)
                pks = shema.extract_pks(logs)
                shema.re_compute(tx, pk_list=pks, sequence=sequence, disabled_commits=disabled)

            def re_compute_values(shema: PropertyValueSchema):
                logs = shema.get_log(tx, commit_id)
                pks = shema.extract_pks(logs)
                shema.re_compute(tx, pk_list=pks, sequence=sequence, disabled_commits=disabled)

            # Structural schemas (file_sources/files/folders/instances) are not logged and
            # never participate in undo/redo — only the editable/logged entities are replayed.
            re_compute(PROPERTY_GROUPS_SCHEMA)
            re_compute(PROPERTIES_SCHEMA)
            re_compute(TAGS_SCHEMA)

            re_compute_values(SHA1_VALUES_SCHEMA)
            re_compute_values(INSTANCE_VALUES_SCHEMA)
            re_compute(INSTANCE_TAG_VALUES_SCHEMA)
            re_compute(SHA1_TAG_VALUES_SCHEMA)


    # TODO: maybe needed later. Or some part needed for database vacuum--- Cascading Logic ---
    # def _cascade_delete_logic(self, tx: Cursor, data: DeleteCommit):
    #     sha1_values: list[Sha1Value] = []
    #     instance_values: list[InstanceValue] = []
    #
    #     if data.tags:
    #         db_tags: list[Tag] = TAGS_SCHEMA.get(tx, id=list(data.tags))
    #         grouping: dict[int, list[Tag]] = defaultdict(list)
    #         for t in db_tags:
    #             grouping[t.list_id].append(t)
    #         db_props: list[Property] = PROPERTIES_SCHEMA.get_latest_logs(tx, tag_list_id=list(grouping.keys()))
    #
    #         action = [-t.id for t in db_tags]
    #
    #         for prop in db_props:
    #             if prop.mode == "sha1":
    #                 values_keys = SHA1_VALUES_SCHEMA.get_all_pk(tx, property_id=prop.id)
    #                 operations = [
    #                     Sha1Value(property_id=p_id, sha1=sha1, value=action, operation=OP_UPDATE) for
    #                     p_id, sha1 in values_keys]
    #                 sha1_values.append(operations)
    #             else:
    #                 values_keys = INSTANCE_VALUES_SCHEMA.get_all_pk(tx, property_id=prop.id)
    #                 operations = [
    #                     InstanceValue(property_id=p_id, instance_id=i_id, value=action, operation=OP_UPDATE) for
    #                     p_id, i_id in values_keys]
    #                 instance_values.append(operations)
    #
    #     return sha1_values, instance_values




    # --- Upsert Handlers (logged entities only) ---

    def _upsert_commit_property_groups(self, tx: Cursor, data: UpsertCommit, commit_id: int, seq_number: int):
        if not data.property_groups: return
        groups = list(data.property_groups.values())
        set_commit(groups, commit_id)

        existing = PROPERTY_GROUPS_SCHEMA.get_index(tx, id=list(data.property_groups.keys()))

        for g in groups:
            g.operation = OP_CREATE if g.id not in existing else OP_UPDATE

        updated = [
            PROPERTY_GROUPS_SCHEMA.merge_logs([existing.get(g.id), g])
            for g in groups
        ]

        PROPERTY_GROUPS_SCHEMA.upsert(tx, objs=updated, sequence=seq_number)
        PROPERTY_GROUPS_SCHEMA.append_log(tx, objs=groups, commit_id=commit_id)

    def _upsert_commit_properties(self, tx: Cursor, data: UpsertCommit, commit_id: int, seq_number: int):
        if not data.properties: return
        properties = list(data.properties.values())
        set_commit(properties, commit_id)

        existing = PROPERTIES_SCHEMA.get_index(tx, id=list(data.properties.keys()))

        for p in properties:
            p.operation = OP_CREATE if p.id not in existing else OP_UPDATE

        updated = [
            PROPERTIES_SCHEMA.merge_logs([existing.get(p.id), p])
            for p in properties
        ]

        PROPERTIES_SCHEMA.upsert(tx, objs=updated, sequence=seq_number)
        PROPERTIES_SCHEMA.append_log(tx, objs=properties, commit_id=commit_id)

    def _upsert_commit_tags(self, tx: Cursor, data: UpsertCommit, commit_id: int, seq_number: int):
        if not data.tags: return
        tags = list(data.tags.values())
        set_commit(tags, commit_id)

        existing = TAGS_SCHEMA.get_index(tx, id=list(data.tags.keys()))

        for t in tags:
            t.operation = OP_CREATE if t.id not in existing else OP_UPDATE

        updated = [
            TAGS_SCHEMA.merge_logs([existing.get(t.id), t])
            for t in tags
        ]

        TAGS_SCHEMA.upsert(tx, objs=updated, sequence=seq_number)
        TAGS_SCHEMA.append_log(tx, objs=tags, commit_id=commit_id)

    def _upsert_commit_instance_values(self, tx: Cursor, data: UpsertCommit, commit_id: int, sequence: int):
        if not data.instance_values:
            return

        p_ids = list(data.instance_values.keys())
        properties = PROPERTIES_SCHEMA.get_index(tx, id=p_ids)

        _tag_dtypes = {PropertyType.tag.value, PropertyType.multi_tags.value}
        all_updates: list[InstanceValue] = []
        final_values: list[InstanceValue] = []

        for prop_id, values in data.instance_values.items():
            prop = properties[prop_id]
            if prop.dtype in _tag_dtypes:
                continue
            final_values.extend(values)
            all_updates.extend(values)

        if final_values:
            INSTANCE_VALUES_SCHEMA.upsert(tx, final_values, sequence=sequence)
        if all_updates:
            INSTANCE_VALUES_SCHEMA.append_log(tx, all_updates, commit_id=commit_id)

    def _upsert_commit_sha1_values(self, tx: Cursor, data: UpsertCommit, commit_id: int, sequence: int):
        if not data.sha1_values:
            return

        p_ids = list(data.sha1_values.keys())
        properties = PROPERTIES_SCHEMA.get_index(tx, id=p_ids)

        _tag_dtypes = {PropertyType.tag.value, PropertyType.multi_tags.value}
        all_updates: list[Sha1Value] = []
        final_values: list[Sha1Value] = []

        for prop_id, values in data.sha1_values.items():
            prop = properties[prop_id]
            if prop.dtype in _tag_dtypes:
                continue
            final_values.extend(values)
            all_updates.extend(values)

        if final_values:
            SHA1_VALUES_SCHEMA.upsert(tx, final_values, sequence=sequence)
        if all_updates:
            SHA1_VALUES_SCHEMA.append_log(tx, all_updates, commit_id=commit_id)

    def _upsert_commit_instance_tag_values(self, tx: Cursor, data: UpsertCommit, commit_id: int, sequence: int):
        if not data.instance_values:
            return

        p_ids = list(data.instance_values.keys())
        properties = PROPERTIES_SCHEMA.get_index(tx, id=p_ids)

        _tag_dtypes = {PropertyType.tag.value, PropertyType.multi_tags.value}
        upsert_rows: list[InstanceTagValue] = []
        log_rows:    list[InstanceTagValue] = []

        for prop_id, values in data.instance_values.items():
            if properties[prop_id].dtype not in _tag_dtypes:
                continue
            for iv in values:
                inst_id     = iv.instance_id
                new_tag_set = set(iv.value or [])

                existing        = INSTANCE_TAG_VALUES_SCHEMA.get(tx, instance_id=inst_id, property_id=prop_id, operation=OP_CREATE)
                existing_active = {r.tag_id for r in existing}

                for tag_id in existing_active - new_tag_set:
                    row = InstanceTagValue(instance_id=inst_id, property_id=prop_id,
                                          tag_id=tag_id, commit_id=commit_id, operation=OP_DELETE)
                    upsert_rows.append(row)
                    log_rows.append(row)

                for tag_id in new_tag_set - existing_active:
                    row = InstanceTagValue(instance_id=inst_id, property_id=prop_id,
                                          tag_id=tag_id, commit_id=commit_id, operation=OP_CREATE)
                    upsert_rows.append(row)
                    log_rows.append(row)

        if upsert_rows:
            INSTANCE_TAG_VALUES_SCHEMA.upsert(tx, upsert_rows, sequence=sequence)
        if log_rows:
            INSTANCE_TAG_VALUES_SCHEMA.append_log(tx, log_rows, commit_id=commit_id)

    def _upsert_commit_sha1_tag_values(self, tx: Cursor, data: UpsertCommit, commit_id: int, sequence: int):
        if not data.sha1_values:
            return

        p_ids = list(data.sha1_values.keys())
        properties = PROPERTIES_SCHEMA.get_index(tx, id=p_ids)

        _tag_dtypes = {PropertyType.tag.value, PropertyType.multi_tags.value}
        upsert_rows: list[Sha1TagValue] = []
        log_rows:    list[Sha1TagValue] = []

        for prop_id, values in data.sha1_values.items():
            if properties[prop_id].dtype not in _tag_dtypes:
                continue
            for sv in values:
                sha1        = sv.sha1
                new_tag_set = set(sv.value or [])

                existing        = SHA1_TAG_VALUES_SCHEMA.get(tx, sha1=sha1, property_id=prop_id, operation=OP_CREATE)
                existing_active = {r.tag_id for r in existing}

                for tag_id in existing_active - new_tag_set:
                    row = Sha1TagValue(sha1=sha1, property_id=prop_id,
                                      tag_id=tag_id, commit_id=commit_id, operation=OP_DELETE)
                    upsert_rows.append(row)
                    log_rows.append(row)

                for tag_id in new_tag_set - existing_active:
                    row = Sha1TagValue(sha1=sha1, property_id=prop_id,
                                      tag_id=tag_id, commit_id=commit_id, operation=OP_CREATE)
                    upsert_rows.append(row)
                    log_rows.append(row)

        if upsert_rows:
            SHA1_TAG_VALUES_SCHEMA.upsert(tx, upsert_rows, sequence=sequence)
        if log_rows:
            SHA1_TAG_VALUES_SCHEMA.append_log(tx, log_rows, commit_id=commit_id)

    def _upsert_commit_file_values(self, tx: Cursor, data: UpsertCommit, commit_id: int, sequence: int):
        if not data.file_values:
            return

        p_ids = list(data.file_values.keys())
        properties = PROPERTIES_SCHEMA.get_index(tx, id=p_ids)

        all_updates: list[FileValue] = []
        merge_updates: list[FileValue] = []
        final_values: list[FileValue] = []

        for prop_id, values in data.file_values.items():
            prop = properties[prop_id]
            if prop.dtype == PropertyType.multi_tags.value:
                merge_updates.extend(values)
            else:
                final_values.extend(values)
            all_updates.extend(values)

        if merge_updates:
            merge_index = FILE_VALUES_SCHEMA.list_to_index(merge_updates)
            db_value_index = FILE_VALUES_SCHEMA.get_by_pk_index(tx, list(merge_index.keys()))
            for pk, value in merge_index.items():
                db_value = db_value_index.get(pk)
                final_value = FILE_VALUES_SCHEMA.merge_logs([db_value, value])
                if final_value:
                    final_values.append(final_value)

        if final_values:
            FILE_VALUES_SCHEMA.upsert(tx, final_values, sequence=sequence)

        FILE_VALUES_SCHEMA.append_log(tx, all_updates, commit_id=commit_id)

    def _cascade_delete_properties(self, tx: Cursor, data: DeleteCommit, commit_id: int, sequence: int):
        if not data.properties:
            return
        properties = PROPERTIES_SCHEMA.get_index(tx, id=list(data.properties))
        _tag_dtypes = {PropertyType.tag.value, PropertyType.multi_tags.value}

        tag_prop_ids     = [pid for pid, p in properties.items() if p.dtype in _tag_dtypes]
        non_tag_prop_ids = [pid for pid, p in properties.items() if p.dtype not in _tag_dtypes]

        if tag_prop_ids:
            self._delete_function(tx, TAGS_SCHEMA,                commit_id, sequence, list_id=tag_prop_ids)
            self._delete_function(tx, INSTANCE_TAG_VALUES_SCHEMA, commit_id, sequence, property_id=tag_prop_ids)
            self._delete_function(tx, SHA1_TAG_VALUES_SCHEMA,     commit_id, sequence, property_id=tag_prop_ids)
        if non_tag_prop_ids:
            self._delete_function(tx, INSTANCE_VALUES_SCHEMA, commit_id, sequence, property_id=non_tag_prop_ids)
            self._delete_function(tx, SHA1_VALUES_SCHEMA,     commit_id, sequence, property_id=non_tag_prop_ids)
            self._delete_function(tx, FILE_VALUES_SCHEMA,     commit_id, sequence, property_id=non_tag_prop_ids)

    def _cascade_delete_tags(self, tx: Cursor, data: DeleteCommit, commit_id: int, sequence: int):
        if not data.tags:
            return
        tag_ids = list(data.tags)
        self._delete_function(tx, INSTANCE_TAG_VALUES_SCHEMA, commit_id, sequence, tag_id=tag_ids)
        self._delete_function(tx, SHA1_TAG_VALUES_SCHEMA,     commit_id, sequence, tag_id=tag_ids)

    @staticmethod
    def _delete_function(tx: Cursor, shema: EntitySchema, commit_id: int, sequence: int, **fields):
        db_objs = shema.get_latest_logs(tx, **fields)
        shema.set_to_delete(objs=db_objs, commit_id=commit_id)
        shema.upsert(tx, objs=db_objs, sequence=sequence)
        shema.append_log(tx, objs=db_objs, commit_id=commit_id)

    # --- SQL Statements ---

    def _exec_get_sequence(self, tx: Cursor) -> int:
        """
        Atomically increments and returns the next sequence ID.
        Requires SQLite 3.35+ for the RETURNING clause.
        """
        # This increments the ID and returns the NEW value in one go
        sql = "UPDATE sequence SET id = id + 1 RETURNING id;"
        tx.execute(sql)
        res = tx.fetchone()

        if res is None:
            # Handle case where the sequence table is empty
            tx.execute("INSERT INTO sequence (id) VALUES (1)")
            return 1

        # Subtract 1 if you want the value BEFORE the increment
        # (standard for most sequence implementations)
        return res[0] - 1