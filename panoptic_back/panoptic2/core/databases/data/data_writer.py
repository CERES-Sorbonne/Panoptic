import datetime
from sqlite3 import Cursor
from typing import Any

from panoptic2.core.databases.data.create import datastore_desc, COMMITS_SCHEMA, FILE_SOURCES_SCHEMA, PROPERTIES_SCHEMA, \
    TAGS_SCHEMA, INSTANCES_SCHEMA, FILES_SCHEMA, FOLDERS_SCHEMA, INSTANCE_VALUES_SCHEMA, SHA1_VALUES_SCHEMA, \
    FILE_VALUES_SCHEMA
from panoptic2.core.databases.entity_schema import EntitySchema, PropertyValueSchema
from panoptic2.core.databases.sqlite_db import SQLiteWriter
from panoptic2.models.models import PropertyType
from panoptic2.core.databases.data.models import (
    Commit, DeleteCommit, UpsertCommit, InstanceValue, Sha1Value, FileValue
)

OP_STAMP_SET = "stamp_set"
OP_STAMP_DIFF = "stamp_diff"

def set_commit(objs: list[Any], commit_id: int):
    for o in objs:
        o.commit_id = commit_id


class DataWriter(SQLiteWriter):
    def __init__(self, path: str):
        super().__init__(path=path, description=datastore_desc)

    def apply_upsert_commit(self, source: str, data: UpsertCommit, group_id: int = None) -> Commit:
        with self.transaction() as tx:
            seq_number = self._exec_get_sequence(tx)
            current_max = tx.execute(f"SELECT COALESCE(MAX(id), 0) FROM {COMMITS_SCHEMA.table}").fetchone()[0]
            commit_id = current_max + 1
            now = datetime.datetime.now()
            if group_id is None:
                group_id = commit_id

            # Process all entity types
            self._upsert_commit_file_sources(tx, data, commit_id, seq_number)
            self._upsert_commit_folders(tx, data, commit_id, seq_number)
            self._upsert_commit_files(tx, data, commit_id, seq_number)
            self._upsert_commit_instances(tx, data, commit_id, seq_number)
            self._upsert_commit_properties(tx, data, commit_id, seq_number)
            self._upsert_commit_tags(tx, data, commit_id, seq_number)
            self._upsert_commit_instance_values(tx, data, commit_id, seq_number)
            self._upsert_commit_sha1_values(tx, data, commit_id, seq_number)
            self._upsert_commit_file_values(tx, data, commit_id, seq_number)

            commit = Commit(id=commit_id, group_id=group_id, source=source, timestamp=now, active=True)
            COMMITS_SCHEMA.upsert(tx, commit, sequence=seq_number)
            return commit

    def apply_delete_commit(self, source: str, data: DeleteCommit, group_id: int = None) -> Commit:
        with self.transaction() as tx:
            sequence = self._exec_get_sequence(tx)
            current_max = tx.execute(f"SELECT COALESCE(MAX(id), 0) FROM {COMMITS_SCHEMA.table}").fetchone()[0]
            commit_id = current_max + 1
            now = datetime.datetime.now()
            if group_id is None:
                group_id = commit_id

            # Not needed for now because we do only logic delete without cleaning the base
            # Process cascade logic first
            # sha1_values, instance_values = self._cascade_delete_logic(tx, data)

            # Handle revert operations for each table using the same pattern as upserts
            if data.file_sources:
                self._delete_function(tx, FILE_SOURCES_SCHEMA, commit_id=commit_id, sequence=sequence,
                                      id=list(data.file_sources))
            if data.folders:
                self._delete_function(tx, FOLDERS_SCHEMA, commit_id=commit_id, sequence=sequence, id=list(data.folders))

            if data.files:
                self._delete_function(tx, FILES_SCHEMA, commit_id=commit_id, sequence=sequence, id=list(data.files))

            if data.instances:
                self._delete_function(tx, INSTANCES_SCHEMA, commit_id=commit_id, sequence=sequence,
                                      id=list(data.instances))
            if data.properties:
                self._delete_function(tx, PROPERTIES_SCHEMA, commit_id=commit_id, sequence=sequence,
                                      id=list(data.properties))
            if data.tags:
                self._delete_function(tx, TAGS_SCHEMA, commit_id=commit_id, sequence=sequence, id=list(data.tags))

            commit = Commit(id=commit_id, group_id=group_id, source=source, timestamp=now, active=True)
            COMMITS_SCHEMA.upsert(tx, commit, sequence=sequence)
            return commit

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
                prop_ids = list({log.property_id for log in logs})
                props = PROPERTIES_SCHEMA.get_latest_logs(tx, id=prop_ids)
                multi_tags_props = {p.id for p in props if p.dtype == PropertyType.multi_tags.value}
                shema.re_compute(tx, pk_list=pks, sequence=sequence, disabled_commits=disabled, multi_tags_property_ids=multi_tags_props)

            re_compute(FILE_SOURCES_SCHEMA)
            re_compute(FILES_SCHEMA)
            re_compute(FOLDERS_SCHEMA)
            re_compute(INSTANCES_SCHEMA)
            re_compute(PROPERTIES_SCHEMA)
            re_compute(TAGS_SCHEMA)

            re_compute_values(SHA1_VALUES_SCHEMA)
            re_compute_values(INSTANCE_VALUES_SCHEMA)


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




    # --- Upsert Handlers ---

    def _upsert_commit_file_sources(self, tx: Cursor, data: UpsertCommit, commit_id: int, seq_number: int):
        if not data.file_sources: return
        sources = list(data.file_sources.values())
        set_commit(sources, commit_id)

        # Get existing state indexed by ID
        existing = FILE_SOURCES_SCHEMA.get_index(tx, id=list(data.file_sources.keys()))

        updated = [
            FILE_SOURCES_SCHEMA.merge_logs([existing.get(s.id), s])
            for s in sources
        ]
        FILE_SOURCES_SCHEMA.upsert(tx, objs=updated, sequence=seq_number)
        FILE_SOURCES_SCHEMA.append_log(tx, objs=sources, commit_id=commit_id)

    def _upsert_commit_folders(self, tx: Cursor, data: UpsertCommit, commit_id: int, seq_number: int):
        if not data.folders: return
        folders = list(data.folders.values())
        set_commit(folders, commit_id)

        existing = FOLDERS_SCHEMA.get_index(tx, id=list(data.folders.keys()))

        updated = [
            FOLDERS_SCHEMA.merge_logs([existing.get(f.id), f])
            for f in folders
        ]

        FOLDERS_SCHEMA.upsert(tx, objs=updated, sequence=seq_number)
        FOLDERS_SCHEMA.append_log(tx, objs=folders, commit_id=commit_id)

    def _upsert_commit_files(self, tx: Cursor, data: UpsertCommit, commit_id: int, seq_number: int):
        if not data.files: return
        files = list(data.files.values())
        set_commit(files, commit_id)

        existing = FILES_SCHEMA.get_index(tx, id=list(data.files.keys()))

        updated = [
            FILES_SCHEMA.merge_logs([existing.get(f.id), f])
            for f in files
        ]

        FILES_SCHEMA.upsert(tx, objs=updated, sequence=seq_number)
        FILES_SCHEMA.append_log(tx, objs=files, commit_id=commit_id)

    def _upsert_commit_instances(self, tx: Cursor, data: UpsertCommit, commit_id: int, seq_number: int):
        if not data.instances: return
        instances = list(data.instances.values())
        set_commit(instances, commit_id)

        existing = INSTANCES_SCHEMA.get_index(tx, id=list(data.instances.keys()))

        updated = [
            INSTANCES_SCHEMA.merge_logs([existing.get(i.id), i])
            for i in instances
        ]

        INSTANCES_SCHEMA.upsert(tx, objs=updated, sequence=seq_number)
        INSTANCES_SCHEMA.append_log(tx, objs=instances, commit_id=commit_id)

    def _upsert_commit_properties(self, tx: Cursor, data: UpsertCommit, commit_id: int, seq_number: int):
        if not data.properties: return
        properties = list(data.properties.values())
        set_commit(properties, commit_id)

        existing = PROPERTIES_SCHEMA.get_index(tx, id=list(data.properties.keys()))

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

        all_updates = []
        merge_updates: list[InstanceValue] = []
        final_values: list[InstanceValue] = []


        for prop_id, values in data.instance_values.items():
            prop = properties[prop_id]
            if prop.dtype == PropertyType.multi_tags.value:
                merge_updates.extend(values)
            else:
                final_values.extend(values)
            all_updates.extend(values)

        merge_index = INSTANCE_VALUES_SCHEMA.list_to_index(merge_updates)
        db_value_index = INSTANCE_VALUES_SCHEMA.get_by_pk_index(tx, merge_index.keys())

        for pk, value in merge_index.items():
            db_value = db_value_index.get(pk)
            final_value = INSTANCE_VALUES_SCHEMA.merge_logs([db_value, value])
            final_values.append(final_value)

        INSTANCE_VALUES_SCHEMA.upsert(tx, final_values, sequence=sequence)
        INSTANCE_VALUES_SCHEMA.append_log(tx, all_updates, commit_id=commit_id)

    def _upsert_commit_sha1_values(self, tx: Cursor, data: UpsertCommit, commit_id: int, sequence: int):
        if not data.sha1_values:
            return

        # 1. Identify properties involved to check for multi_tags dtype
        p_ids = list(data.sha1_values.keys())
        properties = PROPERTIES_SCHEMA.get_index(tx, id=p_ids)

        all_updates: list[Sha1Value] = []
        merge_updates: list[Sha1Value] = []
        final_values: list[Sha1Value] = []

        # 2. Categorize updates based on property type
        for prop_id, values in data.sha1_values.items():
            prop = properties[prop_id]
            # If it's a multi-tag property, we need to merge with existing DB state
            if prop.dtype == PropertyType.multi_tags.value:
                merge_updates.extend(values)
            else:
                final_values.extend(values)
            all_updates.extend(values)

        # 3. Handle Merge (Multi-Tag) logic
        if merge_updates:
            # Index the incoming updates by PK (property_id, sha1)
            merge_index = SHA1_VALUES_SCHEMA.list_to_index(merge_updates)

            # Fetch current values from DB for these specific PKs
            db_value_index = SHA1_VALUES_SCHEMA.get_by_pk_index(tx, list(merge_index.keys()))

            for pk, value in merge_index.items():
                # Get existing state (or None if it's a new entry)
                db_value = db_value_index.get(pk)

                # Replay/fold the value (replay_value returns a new object via replace())
                final_value = SHA1_VALUES_SCHEMA.merge_logs([db_value, value])
                if final_value:
                    final_values.append(final_value)

        # 4. Final Write Operations
        if final_values:
            SHA1_VALUES_SCHEMA.upsert(tx, final_values, sequence=sequence)

        # Log the original intent (all_updates contains the actual OP_ADD/OP_SUB ops)
        SHA1_VALUES_SCHEMA.append_log(tx, all_updates, commit_id=commit_id)

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