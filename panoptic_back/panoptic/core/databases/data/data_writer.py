import datetime
import json
from sqlite3 import Cursor

from panoptic.core.databases.data.create import datastore_desc, COMMITS_SCHEMA, FILE_SOURCES_SCHEMA, PROPERTIES_SCHEMA, \
    TAGS_SCHEMA, INSTANCES_SCHEMA, FILES_SCHEMA, FOLDERS_SCHEMA, INSTANCE_VALUES_SCHEMA, SHA1_VALUES_SCHEMA
from panoptic.core.databases.data.data_reader import DataReader
from panoptic.core.databases.data.helper import EntitySchema
from panoptic.core.databases.sqlite_db import SQLiteWriter
from panoptic.models.data import (
    Commit, DeleteCommit, UpsertCommit, InstanceValue, Sha1Value
)

OP_INSERT = "insert"
OP_UPDATE = "update"
OP_DELETE = "remove"
OP_ADD = "add"
OP_SUB = "del"
OP_SET = "set"


class DataWriter(SQLiteWriter):
    def __init__(self, path: str):
        super().__init__(path=path, description=datastore_desc)
        self.reader = DataReader(path)

    def apply_upsert_commit(self, source: str, data: UpsertCommit, group_id: int = None) -> Commit:
        with self.transaction() as tx:
            current_max = self.reader.get_max_commit_id()
            commit_id = current_max + 1
            now = datetime.datetime.now()
            if group_id is None:
                group_id = commit_id

            # Process all entity types
            self._upsert_commit_file_sources(tx, data, commit_id)
            self._upsert_commit_folders(tx, data, commit_id)
            self._upsert_commit_files(tx, data, commit_id)
            self._upsert_commit_instances(tx, data, commit_id)
            self._upsert_commit_properties(tx, data, commit_id)
            self._upsert_commit_tags(tx, data, commit_id)
            self._upsert_commit_instance_values(tx, data, commit_id)
            self._upsert_commit_sha1_values(tx, data, commit_id)

            commit = Commit(id=commit_id, group_id=group_id, source=source, timestamp=now)
            COMMITS_SCHEMA.upserts(tx, commit)
            return commit

    def apply_delete_commit(self, source: str, data: DeleteCommit, group_id: int = None) -> Commit:
        with self.transaction() as tx:
            current_max = self.reader.get_max_commit_id()
            commit_id = current_max + 1
            now = datetime.datetime.now()
            if group_id is None:
                group_id = commit_id

            # Process cascade logic first
            self._cascade_delete_logic(data)

            # Handle values deletion with proper revert
            if data.properties:
                self._exec_bulk_delete_values_with_revert(tx, INSTANCE_VALUES_SCHEMA, data.properties, commit_id)
                self._exec_bulk_delete_values_with_revert(tx, SHA1_VALUES_SCHEMA, data.properties, commit_id)

            # Handle revert operations for each table using the same pattern as upserts
            if data.file_sources:
                self._exec_bulk_delete_with_revert(tx, FILE_SOURCES_SCHEMA, "id", data.file_sources, commit_id)
            if data.folders:
                self._exec_bulk_delete_with_revert(tx, FOLDERS_SCHEMA, "id", data.folders, commit_id)
            if data.files:
                self._exec_bulk_delete_with_revert(tx, FILES_SCHEMA, "id", data.files, commit_id)
            if data.instances:
                self._exec_bulk_delete_with_revert(tx, INSTANCES_SCHEMA, "id", data.instances, commit_id)
            if data.properties:
                self._exec_bulk_delete_with_revert(tx, PROPERTIES_SCHEMA, "id", data.properties, commit_id)
            if data.tags:
                self._exec_bulk_delete_with_revert(tx, TAGS_SCHEMA, "id", data.tags, commit_id)

            commit = Commit(id=commit_id, group_id=group_id, source=source, timestamp=now)
            COMMITS_SCHEMA.upserts(tx, commit)
            return commit

    # --- Cascading Logic ---

    def _cascade_delete_logic(self, data: DeleteCommit):
        if data.file_sources:
            folders = self.reader.get_folders(source_id=list(data.file_sources))
            data.folders.update(row.id for row in folders)

        if data.folders:
            frontier = list(data.folders)
            while frontier:
                children = self.reader.get_folders(parent=frontier)
                new_fids = [child.id for child in children if child.id not in data.folders]
                if not new_fids:
                    break
                data.folders.update(new_fids)
                frontier = new_fids

        if data.folders:
            files = self.reader.get_files(folder_id=list(data.folders))
            data.files.update(row.id for row in files)

        if data.files:
            instances = self.reader.get_instances(file_id=list(data.files))
            data.instances.update(row.id for row in instances)

        # if data.properties:
        #     tags = self.reader.get_tags(property_id=list(data.properties))
        #     data.tags.update(row.id for row in tags)

    # --- Upsert Handlers ---

    def _upsert_commit_file_sources(self, tx: Cursor, data: UpsertCommit, commit_id: int):
        if not data.file_sources: return
        ids = list(data.file_sources.keys())
        existing = {row.id: row for row in self.reader.get_file_sources(id=ids)}
        update_list, revert_list = [], []

        for obj in data.file_sources.values():
            obj.commit_id = commit_id
            if obj.id in existing:
                revert_list.append((existing[obj.id], OP_UPDATE))
            else:
                revert_list.append((obj, OP_INSERT))
            update_list.append(obj)

        FILE_SOURCES_SCHEMA.upserts(tx, objs=update_list, commit_id=commit_id)
        FILE_SOURCES_SCHEMA.insert_revert_operations(tx, ops=revert_list, revert_commit_id=commit_id)

    def _upsert_commit_folders(self, tx: Cursor, data: UpsertCommit, commit_id: int):
        if not data.folders: return
        ids = list(data.folders.keys())
        existing = {row.id: row for row in self.reader.get_folders(id=ids)}
        update_list, revert_list = [], []

        for obj in data.folders.values():
            obj.commit_id = commit_id
            if obj.id in existing:
                revert_list.append((existing[obj.id], OP_UPDATE))
            else:
                revert_list.append((obj, OP_INSERT))
            update_list.append(obj)

        FOLDERS_SCHEMA.upserts(tx, objs=update_list, commit_id=commit_id)
        FOLDERS_SCHEMA.insert_revert_operations(tx, ops=revert_list, revert_commit_id=commit_id)

    def _upsert_commit_files(self, tx: Cursor, data: UpsertCommit, commit_id: int):
        if not data.files: return
        ids = list(data.files.keys())
        existing = {row.id: row for row in self.reader.get_files(id=ids)}
        update_list, revert_list = [], []

        for obj in data.files.values():
            obj.commit_id = commit_id
            if obj.id in existing:
                revert_list.append((existing[obj.id], OP_UPDATE))
            else:
                revert_list.append((obj, OP_INSERT))
            update_list.append(obj)

        FILES_SCHEMA.upserts(tx, objs=update_list, commit_id=commit_id)
        FILES_SCHEMA.insert_revert_operations(tx, ops=revert_list, revert_commit_id=commit_id)

    def _upsert_commit_instances(self, tx: Cursor, data: UpsertCommit, commit_id: int):
        if not data.instances: return
        ids = list(data.instances.keys())
        existing = {row.id: row for row in self.reader.get_instances(id=ids)}
        update_list, revert_list = [], []

        for obj in data.instances.values():
            obj.commit_id = commit_id
            if obj.id in existing:
                revert_list.append((existing[obj.id], OP_UPDATE))
            else:
                revert_list.append((obj, OP_INSERT))
            update_list.append(obj)

        INSTANCES_SCHEMA.upserts(tx, objs=update_list, commit_id=commit_id)
        INSTANCES_SCHEMA.insert_revert_operations(tx, ops=revert_list, revert_commit_id=commit_id)

    def _upsert_commit_properties(self, tx: Cursor, data: UpsertCommit, commit_id: int):
        if not data.properties: return
        ids = list(data.properties.keys())
        existing = {row.id: row for row in self.reader.get_properties(id=ids)}
        update_list, revert_list = [], []

        for obj in data.properties.values():
            obj.commit_id = commit_id
            if obj.id in existing:
                revert_list.append((existing[obj.id], OP_UPDATE))
            else:
                revert_list.append((obj, OP_INSERT))
            update_list.append(obj)

        PROPERTIES_SCHEMA.upserts(tx, objs=update_list, commit_id=commit_id)
        PROPERTIES_SCHEMA.insert_revert_operations(tx, ops=revert_list, revert_commit_id=commit_id)

    def _upsert_commit_tags(self, tx: Cursor, data: UpsertCommit, commit_id: int):
        if not data.tags: return
        ids = list(data.tags.keys())
        existing = {row.id: row for row in self.reader.get_tags(id=ids)}
        update_list, revert_list = [], []

        for obj in data.tags.values():
            obj.commit_id = commit_id
            if obj.id in existing:
                revert_list.append((existing[obj.id], OP_UPDATE))
            else:
                revert_list.append((obj, OP_INSERT))
            update_list.append(obj)

        TAGS_SCHEMA.upserts(tx, objs=update_list, commit_id=commit_id)
        TAGS_SCHEMA.insert_revert_operations(tx, ops=revert_list, revert_commit_id=commit_id)

    def _upsert_commit_instance_values(self, tx: Cursor, data: UpsertCommit, commit_id: int):
        if not data.instance_values:
            return

        p_ids = list(data.instance_values.keys())
        properties = {p.id: p for p in self.reader.get_properties(id=p_ids)}
        for p in data.properties.values():
            properties[p.id] = p

        existing_list = self.reader.get_instance_values(property_id=p_ids)
        existing = {(r.property_id, r.instance_id): r for r in existing_list}

        update_list, revert_list = [], []

        for p_id, prop_write in data.instance_values.items():
            prop = properties[p_id]
            mode = prop_write.stamp_mode

            for idx, i_id in enumerate(prop_write.keys):
                key = (p_id, i_id)
                current_obj = existing.get(key)
                current_val_raw = current_obj.value if current_obj else None

                if mode is None or mode == OP_SET:
                    val = prop_write.values[idx] if mode is None else prop_write.values
                    new_val_db = val
                    revert_op = OP_UPDATE
                elif mode == OP_ADD and prop.dtype == 'multi_tags':
                    tags = set(current_val_raw) if current_val_raw else set()
                    to_add = prop_write.values
                    tags.update([to_add] if isinstance(to_add, str) else to_add)
                    new_val_db = sorted(list(tags))
                    revert_op = OP_SUB
                elif mode == OP_SUB and prop.dtype == 'multi_tags':
                    tags = set(current_val_raw) if current_val_raw else set()
                    to_remove = prop_write.values[idx]
                    tags.difference_update([to_remove] if isinstance(to_remove, str) else to_remove)
                    new_val_db = sorted(list(tags))
                    revert_op = OP_ADD
                else:
                    continue

                new_obj = InstanceValue(property_id=p_id, instance_id=i_id, value=new_val_db, commit_id=commit_id)
                update_list.append(new_obj)

                revert_source = current_obj if current_obj else InstanceValue(
                    property_id=p_id, instance_id=i_id, value=current_val_raw, commit_id=commit_id
                )
                revert_list.append((revert_source, revert_op))

        if update_list:
            INSTANCE_VALUES_SCHEMA.upserts(tx, objs=update_list, commit_id=commit_id)
            INSTANCE_VALUES_SCHEMA.insert_revert_operations(tx, ops=revert_list, revert_commit_id=commit_id)

    def _upsert_commit_sha1_values(self, tx: Cursor, data: UpsertCommit, commit_id: int):
        if not data.sha1_values:
            return

        p_ids = list(data.sha1_values.keys())
        properties = {p.id: p for p in self.reader.get_properties(id=p_ids)}
        for p in data.properties.values():
            properties[p.id] = p

        existing_list = self.reader.get_sha1_values(property_id=p_ids)
        existing = {(r.property_id, r.sha1): r for r in existing_list}

        update_list, revert_list = [], []

        for p_id, prop_write in data.sha1_values.items():
            prop = properties[p_id]
            mode = prop_write.stamp_mode

            for idx, sha1 in enumerate(prop_write.keys):
                key = (p_id, sha1)
                current_obj = existing.get(key)
                current_val_raw = current_obj.value if current_obj else None

                if mode is None or mode == OP_SET:
                    new_val_db = prop_write.values[idx] if mode is None else prop_write.values
                    revert_op = OP_UPDATE
                elif mode == OP_ADD and prop.dtype == 'multi_tags':
                    tags = set(current_val_raw) if current_val_raw else set()
                    to_add = prop_write.values
                    tags.update([to_add] if isinstance(to_add, str) else to_add)
                    new_val_db = sorted(list(tags))
                    revert_op = OP_SUB
                elif mode == OP_SUB and prop.dtype == 'multi_tags':
                    tags = set(current_val_raw) if current_val_raw else set()
                    to_remove = prop_write.values[idx]
                    tags.difference_update([to_remove] if isinstance(to_remove, str) else to_remove)
                    new_val_db = sorted(list(tags))
                    revert_op = OP_ADD
                else:
                    continue

                new_obj = Sha1Value(property_id=p_id, sha1=sha1, value=new_val_db, commit_id=commit_id)
                update_list.append(new_obj)

                revert_source = current_obj if current_obj else Sha1Value(
                    property_id=p_id, sha1=sha1, value=current_val_raw, commit_id=commit_id
                )
                revert_list.append((revert_source, revert_op))

        if update_list:
            SHA1_VALUES_SCHEMA.upserts(tx, objs=update_list, commit_id=commit_id)
            SHA1_VALUES_SCHEMA.insert_revert_operations(tx, ops=revert_list, revert_commit_id=commit_id)

    def _exec_bulk_delete_with_revert(self, tx: Cursor, schema: EntitySchema, field: str, ids: set,
                                      revert_commit_id: int):
        """Delete records and create revert operations in the corresponding _reverts table"""
        if not ids:
            return

        # Get records to be deleted
        rows = schema.get(tx, **{f"{field}": list(ids)})

        if not rows:
            return

        # Get column names for the revert table (same columns + commit_id, revert_commit_id, operation)
        table_name = schema.table
        column_names = [c.name for c in schema.columns]

        # Create revert records (must include all columns + commit_id, revert_commit_id, operation)
        revert_rows = []
        for row in rows:
            if isinstance(row, tuple):
                # For tuple result
                row_data = list(row)
                revert_row = row_data + [revert_commit_id, OP_DELETE]  # commit_id from original table is already there
                revert_rows.append(revert_row)
            else:
                # For struct/other type - convert to list and add revert fields
                row_data = list(row) if hasattr(row, '__iter__') and not isinstance(row, str) else [row]
                revert_row = row_data + [revert_commit_id, OP_DELETE]
                revert_rows.append(revert_row)

        # Build the INSERT statement for reverts table
        columns_for_revert = column_names + ["commit_id", "revert_commit_id", "operation"]
        placeholders_for_revert = "(" + ", ".join(["?"] * len(columns_for_revert)) + ")"
        revert_sql = f"INSERT INTO {table_name}_reverts ({', '.join(columns_for_revert)}) VALUES {placeholders_for_revert}"

        # Execute revert inserts
        if revert_rows:
            tx.executemany(revert_sql, revert_rows)

        # Delete from original table
        schema.deletes(tx, [(getattr(row, field) if hasattr(row, field) else row[0]) for row in rows])

    def _exec_bulk_delete_values_with_revert(self, tx: Cursor, schema: EntitySchema, property_ids: set,
                                             revert_commit_id: int):
        """Delete values and create revert operations for value tables"""
        if not property_ids:
            return

        # Get records to be deleted
        if hasattr(schema, 'table') and 'sha1' in schema.table:
            # For sha1_values - get by property_id
            rows = schema.get(tx, property_id=list(property_ids))
        else:
            # For instance_values - get by property_id
            rows = schema.get(tx, property_id=list(property_ids))

        if not rows:
            return

        # Get column names for the revert table
        table_name = schema.table
        column_names = [c.name for c in schema.columns]

        # Create revert records
        revert_rows = []
        for row in rows:
            if isinstance(row, tuple):
                # For tuple result
                row_data = list(row)
                revert_row = row_data + [revert_commit_id, OP_DELETE]
                revert_rows.append(revert_row)
            else:
                # For struct/other type
                row_data = list(row) if hasattr(row, '__iter__') and not isinstance(row, str) else [row]
                revert_row = row_data + [revert_commit_id, OP_DELETE]
                revert_rows.append(revert_row)

        # Build the INSERT statement for reverts table
        columns_for_revert = column_names + ["commit_id", "revert_commit_id", "operation"]
        placeholders_for_revert = "(" + ", ".join(["?"] * len(columns_for_revert)) + ")"
        revert_sql = f"INSERT INTO {table_name}_reverts ({', '.join(columns_for_revert)}) VALUES {placeholders_for_revert}"

        # Execute revert inserts
        if revert_rows:
            tx.executemany(revert_sql, revert_rows)

        # Delete from original table
        schema.deletes(tx, property_ids)
    # --- SQL Statements ---


    @staticmethod
    def _exec_bulk_delete(tx: Cursor, table: str, field: str, ids: set, commit_id: int):
        if not ids:
            return

        tx.execute(f"CREATE TEMP TABLE _staging AS SELECT * FROM {table} WHERE 0")

        tx.execute("CREATE TEMP TABLE _del_ids (id ANY)")
        tx.executemany("INSERT INTO _del_ids VALUES (?)", [(i,) for i in ids])

        tx.execute(f"""
            INSERT INTO _staging 
            SELECT * FROM {table} 
            WHERE {field} IN (SELECT id FROM _del_ids)
        """)

        tx.execute("UPDATE _staging SET commit_id = ?", (commit_id,))

        tx.execute(f"INSERT INTO {table}_reverts SELECT *, ? FROM _staging", (OP_DELETE,))

        tx.execute(f"DELETE FROM {table} WHERE {field} IN (SELECT id FROM _del_ids)")

        tx.execute("DROP TABLE _staging")
        tx.execute("DROP TABLE _del_ids")

    @staticmethod
    def _exec_bulk_delete_values(tx: Cursor, schema: EntitySchema, property_ids: set, revert_commit_id: int):
        if not property_ids:
            return

        rows = schema.get(tx, property_id=list(property_ids))
        if not rows:
            return

        revert_col_names = [c.name for c in schema.columns] + ["commit_id", "revert_commit_id", "operation"]
        revert_placeholders = "(" + ", ".join(["?"] * len(revert_col_names)) + ")"
        revert_sql = f"INSERT INTO {schema.table}_reverts ({', '.join(revert_col_names)}) VALUES {', '.join([revert_placeholders] * len(rows))}"

        params = []
        for row in rows:
            params.extend(row)
            params.append(revert_commit_id)
            params.append(OP_DELETE)
        tx.execute(revert_sql, params)

        schema.deletes(tx, [(row[0], row[1]) for row in rows])

    @staticmethod
    def _sql_insert_commit(tx: Cursor, commit_id: int, group_id: int, source: str, now: datetime.datetime):
        tx.execute("INSERT INTO commits (id, group_id, source, timestamp) VALUES (?, ?, ?, ?)",
                   (commit_id, group_id, source, now.isoformat()))

    @staticmethod
    def _sql_upsert_file_sources(tx, b):
        tx.executemany("INSERT OR REPLACE INTO file_sources (id,dtype,name,root_url,commit_id) VALUES (?,?,?,?,?)", b)

    @staticmethod
    def _sql_insert_file_sources_history(tx, b):
        tx.executemany(
            "INSERT INTO file_sources_history (id,dtype,name,root_url,commit_id,operation_type) VALUES (?,?,?,?,?,?)", b)

    @staticmethod
    def _sql_upsert_folders(tx, b):
        tx.executemany("INSERT OR REPLACE INTO folders (id,source_id,path,name,parent,commit_id) VALUES (?,?,?,?,?,?)",
                       b)

    @staticmethod
    def _sql_insert_folders_history(tx, b):
        tx.executemany(
            "INSERT INTO folders_history (id,source_id,path,name,parent,commit_id,operation_type) VALUES (?,?,?,?,?,?,?)",
            b)

    @staticmethod
    def _sql_upsert_files(tx, b):
        tx.executemany("INSERT OR REPLACE INTO files (id,name,folder_id,sha1,commit_id) VALUES (?,?,?,?,?)", b)

    @staticmethod
    def _sql_insert_files_history(tx, b):
        tx.executemany(
            "INSERT INTO files_history (id,name,folder_id,sha1,commit_id,operation_type) VALUES (?,?,?,?,?,?)", b)

    @staticmethod
    def _sql_upsert_instances(tx, b):
        tx.executemany("INSERT OR REPLACE INTO instances (id,file_id,sha1,commit_id) VALUES (?,?,?,?)", b)

    @staticmethod
    def _sql_insert_instances_history(tx, b):
        tx.executemany("INSERT INTO instances_history (id,file_id,sha1,commit_id,operation_type) VALUES (?,?,?,?,?)", b)

    @staticmethod
    def _sql_upsert_properties(tx, b):
        tx.executemany("INSERT OR REPLACE INTO properties (id,dtype,mode,name,access,layer, commit_id) VALUES (?,?,?,?,?,?,?)", b)

    @staticmethod
    def _sql_insert_properties_history(tx, b):
        tx.executemany(
            "INSERT INTO properties_history (id,dtype,mode,name,access,layer,commit_id,operation_type) VALUES (?,?,?,?,?,?,?,?)", b)

    @staticmethod
    def _sql_upsert_tags(tx, b):
        tx.executemany(
            "INSERT OR REPLACE INTO tags (id,property_id,parents,value,color,commit_id) VALUES (?,?,?,?,?,?)", b)

    @staticmethod
    def _sql_insert_tags_history(tx, b):
        tx.executemany(
            "INSERT INTO tags_history (id,property_id,parents,value,color,commit_id,operation_type) VALUES (?,?,?,?,?,?,?)",
            b)

    @staticmethod
    def _sql_upsert_instance_values(tx, b):
        tx.executemany(
            "INSERT OR REPLACE INTO instance_values (property_id,instance_id,value,commit_id) VALUES (?,?,?,?)", b)

    @staticmethod
    def _sql_insert_instance_values_history(tx, b):
        tx.executemany(
            "INSERT INTO instance_values_history (property_id,instance_id,value,commit_id,operation_type) VALUES (?,?,?,?,?)",
            b)

    @staticmethod
    def _sql_upsert_sha1_values(tx, b):
        tx.executemany("INSERT OR REPLACE INTO sha1_values (property_id,sha1,value,commit_id) VALUES (?,?,?,?)", b)

    @staticmethod
    def _sql_insert_sha1_values_history(tx, b):
        tx.executemany(
            "INSERT INTO sha1_values_history (property_id,sha1,value,commit_id,operation_type) VALUES (?,?,?,?,?)", b)