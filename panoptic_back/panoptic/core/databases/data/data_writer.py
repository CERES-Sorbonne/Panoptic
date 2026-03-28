import datetime
import json
from sqlite3 import Cursor

from panoptic.core.databases.data.create import datastore_desc
from panoptic.core.databases.data.data_reader import DataReader
from panoptic.core.databases.sqlite_db import SQLiteWriter
from panoptic.models.data import (
    Commit, DeleteCommit, UpsertCommit
)

OP_INSERT = 1
OP_UPDATE = 2
OP_DELETE = 3
OP_ADD = 4
OP_SUB = 5


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

            self._sql_insert_commit(tx, commit_id, group_id, source, now)
            return Commit(id=commit_id, group_id=group_id, source=source, timestamp=now)

    def apply_delete_commit(self, source: str, data: DeleteCommit, group_id: int = None) -> Commit:
        with self.transaction() as tx:
            current_max = self.reader.get_max_commit_id()
            commit_id = current_max + 1
            now = datetime.datetime.now()
            if group_id is None:
                group_id = commit_id

            self._cascade_delete_logic(data)

            self._exec_bulk_delete(tx, "file_sources", "id", data.file_sources, commit_id)
            self._exec_bulk_delete(tx, "folders", "id", data.folders, commit_id)
            self._exec_bulk_delete(tx, "files", "id", data.files, commit_id)
            self._exec_bulk_delete(tx, "instances", "id", data.instances, commit_id)
            self._exec_bulk_delete(tx, "properties", "id", data.properties, commit_id)
            self._exec_bulk_delete(tx, "tags", "id", data.tags, commit_id)

            self._sql_insert_commit(tx, commit_id, group_id, source, now)
            return Commit(id=commit_id, group_id=group_id, source=source, timestamp=now)

    # --- Cascading Logic ---

    def _cascade_delete_logic(self, data: DeleteCommit):
        if data.file_sources:
            rows = self.reader.get_folders(source_id=list(data.file_sources))
            data.folders.update(row.id for row in rows)

        pending = list(data.folders)
        processed = set()
        while pending:
            fid = pending.pop()
            if fid in processed: continue
            processed.add(fid)

            subs = self.reader.get_folders(parent=fid)
            for s in subs:
                data.folders.add(s.id)
                pending.append(s.id)

            files = self.reader.get_files(folder_id=fid)
            data.files.update(f.id for f in files)

        if data.files:
            rows = self.reader.get_instances(file_id=list(data.files))
            data.instances.update(row.id for row in rows)

    # --- Upsert Handlers ---

    def _upsert_commit_file_sources(self, tx: Cursor, data: UpsertCommit, commit_id: int):
        if not data.file_sources: return
        ids = list(data.file_sources.keys())
        existing = {row.id: row for row in self.reader.get_file_sources(id=ids)}
        u_batch, h_batch = [], []

        for obj in data.file_sources.values():
            rev_op = OP_UPDATE if obj.id in existing else OP_DELETE
            u_batch.append((obj.id, obj.dtype, obj.name, obj.root_url, commit_id))
            if rev_op == OP_DELETE:
                h_batch.append((obj.id, None, None, None, commit_id, rev_op))
            else:
                d = existing[obj.id]
                h_batch.append((obj.id, d.dtype, d.name, d.root_url, commit_id, rev_op))

        if u_batch:
            self._sql_upsert_file_sources(tx, u_batch)
            self._sql_insert_file_sources_history(tx, h_batch)

    def _upsert_commit_folders(self, tx: Cursor, data: UpsertCommit, commit_id: int):
        if not data.folders: return
        ids = list(data.folders.keys())
        existing = {row.id: row for row in self.reader.get_folders(id=ids)}
        u_batch, h_batch = [], []

        for obj in data.folders.values():
            rev_op = OP_UPDATE if obj.id in existing else OP_DELETE
            u_batch.append((obj.id, obj.source_id, obj.path, obj.name, obj.parent, commit_id))
            if rev_op == OP_DELETE:
                h_batch.append((obj.id, None, None, None, None, commit_id, rev_op))
            else:
                d = existing[obj.id]
                h_batch.append((obj.id, d.source_id, d.path, d.name, d.parent, commit_id, rev_op))

        if u_batch:
            self._sql_upsert_folders(tx, u_batch)
            self._sql_insert_folders_history(tx, h_batch)

    def _upsert_commit_files(self, tx: Cursor, data: UpsertCommit, commit_id: int):
        if not data.files: return
        ids = list(data.files.keys())
        existing = {row.id: row for row in self.reader.get_files(id=ids)}
        u_batch, h_batch = [], []

        for obj in data.files.values():
            rev_op = OP_UPDATE if obj.id in existing else OP_DELETE
            u_batch.append((obj.id, obj.name, obj.folder_id, obj.sha1, commit_id))
            if rev_op == OP_DELETE:
                h_batch.append((obj.id, None, None, None, commit_id, rev_op))
            else:
                d = existing[obj.id]
                h_batch.append((obj.id, d.name, d.folder_id, d.sha1, commit_id, rev_op))

        if u_batch:
            self._sql_upsert_files(tx, u_batch)
            self._sql_insert_files_history(tx, h_batch)

    def _upsert_commit_instances(self, tx: Cursor, data: UpsertCommit, commit_id: int):
        if not data.instances: return
        ids = list(data.instances.keys())
        existing = {row.id: row for row in self.reader.get_instances(id=ids)}
        u_batch, h_batch = [], []

        for obj in data.instances.values():
            rev_op = OP_UPDATE if obj.id in existing else OP_DELETE
            u_batch.append((obj.id, obj.file_id, obj.sha1, commit_id))
            if rev_op == OP_DELETE:
                h_batch.append((obj.id, None, None, commit_id, rev_op))
            else:
                d = existing[obj.id]
                h_batch.append((obj.id, d.file_id, d.sha1, commit_id, rev_op))

        if u_batch:
            self._sql_upsert_instances(tx, u_batch)
            self._sql_insert_instances_history(tx, h_batch)

    def _upsert_commit_properties(self, tx: Cursor, data: UpsertCommit, commit_id: int):
        if not data.properties: return
        ids = list(data.properties.keys())
        existing = {row.id: row for row in self.reader.get_properties(id=ids)}
        u_batch, h_batch = [], []

        for obj in data.properties.values():
            rev_op = OP_UPDATE if obj.id in existing else OP_DELETE
            u_batch.append((obj.id, obj.dtype, obj.mode, obj.name, commit_id))
            if rev_op == OP_DELETE:
                h_batch.append((obj.id, None, None, None, commit_id, rev_op))
            else:
                d = existing[obj.id]
                h_batch.append((obj.id, d.dtype, d.mode, d.name, commit_id, rev_op))

        if u_batch:
            self._sql_upsert_properties(tx, u_batch)
            self._sql_insert_properties_history(tx, h_batch)

    def _upsert_commit_tags(self, tx: Cursor, data: UpsertCommit, commit_id: int):
        if not data.tags: return
        ids = list(data.tags.keys())
        existing = {row.id: row for row in self.reader.get_tags(id=ids)}
        u_batch, h_batch = [], []

        for obj in data.tags.values():
            rev_op = OP_UPDATE if obj.id in existing else OP_DELETE
            p_json = json.dumps(obj.parents) if obj.parents else "[]"
            u_batch.append((obj.id, obj.property_id, p_json, obj.value, obj.color, commit_id))
            if rev_op == OP_DELETE:
                h_batch.append((obj.id, None, None, None, None, commit_id, rev_op))
            else:
                d = existing[obj.id]
                d_parents_json = json.dumps(d.parents) if d.parents else "[]"
                h_batch.append((obj.id, d.property_id, d_parents_json, d.value, d.color, commit_id, rev_op))

        if u_batch:
            self._sql_upsert_tags(tx, u_batch)
            self._sql_insert_tags_history(tx, h_batch)

    def _upsert_commit_instance_values(self, tx: Cursor, data: UpsertCommit, commit_id: int):
        if not data.instance_values: return
        p_ids = list(data.instance_values.keys())
        existing_list = self.reader.get_instance_values(property_id=p_ids)
        existing = {(r.property_id, r.instance_id): r for r in existing_list}
        u_batch, h_batch = [], []

        for p_id, prop_write in data.instance_values.items():
            mode = prop_write.stamp_mode
            if mode is None:
                for idx, i_id in enumerate(prop_write.keys):
                    key = (p_id, i_id)
                    val = prop_write.values[idx]
                    val_db = json.dumps(val) if isinstance(val, (dict, list)) else val
                    u_batch.append((p_id, i_id, val_db, commit_id))
                    prev_val = existing[key].value if key in existing else None
                    h_batch.append((p_id, i_id, prev_val, commit_id, OP_UPDATE))
            elif mode == 'set':
                for i_id in prop_write.keys:
                    key = (p_id, i_id)
                    val = prop_write.values
                    val_db = json.dumps(val) if isinstance(val, (dict, list)) else val
                    u_batch.append((p_id, i_id, val_db, commit_id))
                    prev_val = existing[key].value if key in existing else None
                    h_batch.append((p_id, i_id, prev_val, commit_id, OP_UPDATE))

        if u_batch:
            self._sql_upsert_instance_values(tx, u_batch)
            self._sql_insert_instance_values_history(tx, h_batch)

    def _upsert_commit_sha1_values(self, tx: Cursor, data: UpsertCommit, commit_id: int):
        if not data.sha1_values:
            return

        p_ids = list(data.sha1_values.keys())
        properties = {p.id: p for p in self.reader.get_properties(id=p_ids)}
        existing_list = self.reader.get_sha1_values(property_id=p_ids)
        existing = {(r.property_id, r.sha1): r for r in existing_list}
        u_batch, h_batch = [], []

        for p_id, prop_write in data.sha1_values.items():
            prop = properties[p_id]
            mode = prop_write.stamp_mode
            if mode is None:
                for idx, sha1 in enumerate(prop_write.keys):
                    key = (p_id, sha1)
                    val = prop_write.values[idx]
                    val_db = json.dumps(val)
                    u_batch.append((p_id, sha1, val_db, commit_id))
                    prev_val = existing[key].value if key in existing else None
                    h_batch.append((p_id, sha1, prev_val, commit_id, OP_UPDATE))
            elif mode == 'set':
                for sha1 in prop_write.keys:
                    key = (p_id, sha1)
                    val = prop_write.values
                    val_db = json.dumps(val)
                    u_batch.append((p_id, sha1, val_db, commit_id))
                    prev_val = existing[key].value if key in existing else None
                    h_batch.append((p_id, sha1, prev_val, commit_id, OP_UPDATE))
            elif mode == 'add' and prop.dtype == 'multi_tags':
                for idx, sha1 in enumerate(prop_write.keys):
                    key = (p_id, sha1)

                    # Get current state
                    current_val_raw = existing[key].value if key in existing else "[]"
                    try:
                        current_tags = set(json.loads(current_val_raw))
                    except (json.JSONDecodeError, TypeError):
                        current_tags = set()

                    # Determine tags to add (handles single string or list of strings)
                    to_add = prop_write.values
                    if isinstance(to_add, str):
                        current_tags.add(to_add)
                    else:
                        current_tags.update(to_add)

                    new_val_db = json.dumps(sorted(list(current_tags)))
                    u_batch.append((p_id, sha1, new_val_db, commit_id))

                    # History records the state BEFORE the addition
                    h_batch.append((p_id, sha1, current_val_raw, commit_id, OP_ADD))

            elif mode == 'sub' and prop.dtype == 'multi_tags':
                for idx, sha1 in enumerate(prop_write.keys):
                    key = (p_id, sha1)

                    # If it doesn't exist, there's nothing to subtract from
                    if key not in existing:
                        continue

                    current_val_raw = existing[key].value
                    try:
                        current_tags = set(json.loads(current_val_raw))
                    except (json.JSONDecodeError, TypeError):
                        continue

                    # Determine tags to remove
                    to_remove = prop_write.values[idx]
                    if isinstance(to_remove, str):
                        current_tags.discard(to_remove)
                    else:
                        current_tags.difference_update(to_remove)

                    new_val_db = json.dumps(sorted(list(current_tags)))
                    u_batch.append((p_id, sha1, new_val_db, commit_id))

                    # History records the state BEFORE the subtraction
                    h_batch.append((p_id, sha1, current_val_raw, commit_id, OP_SUB))

        if u_batch:
            self._sql_upsert_sha1_values(tx, u_batch)
            self._sql_insert_sha1_values_history(tx, h_batch)

    # --- SQL Statements ---

    @staticmethod
    def _exec_bulk_delete(tx: Cursor, table: str, field: str, ids: set, commit_id: int):
        if not ids: return
        tx.execute("CREATE TEMP TABLE _del_ids (id ANY)")
        tx.executemany("INSERT INTO _del_ids VALUES (?)", [(i,) for i in ids])

        tx.execute(f"""
            INSERT INTO {table}_history
            SELECT *, ?, {OP_DELETE} FROM {table}
            WHERE {field} IN (SELECT id FROM _del_ids)
        """, (commit_id,))

        tx.execute(f"DELETE FROM {table} WHERE {field} IN (SELECT id FROM _del_ids)")
        tx.execute("DROP TABLE _del_ids")

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
        tx.executemany("INSERT OR REPLACE INTO properties (id,dtype,mode,name,commit_id) VALUES (?,?,?,?,?)", b)

    @staticmethod
    def _sql_insert_properties_history(tx, b):
        tx.executemany(
            "INSERT INTO properties_history (id,dtype,mode,name,commit_id,operation_type) VALUES (?,?,?,?,?,?)", b)

    @staticmethod
    def _sql_upsert_tags(tx, b):
        tx.executemany(
            "INSERT OR REPLACE INTO tags (id,property_id,parents,name,color,commit_id) VALUES (?,?,?,?,?,?)", b)

    @staticmethod
    def _sql_insert_tags_history(tx, b):
        tx.executemany(
            "INSERT INTO tags_history (id,property_id,parents,name,color,commit_id,operation_type) VALUES (?,?,?,?,?,?,?)",
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