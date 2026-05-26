from typing import List

from panoptic.core.databases.data.create import (
    COMMITS_SCHEMA, FILE_SOURCES_SCHEMA, FOLDERS_SCHEMA, FILES_SCHEMA,
    INSTANCES_SCHEMA, PROPERTIES_SCHEMA, TAGS_SCHEMA,
    INSTANCE_VALUES_SCHEMA, SHA1_VALUES_SCHEMA, FILE_VALUES_SCHEMA
)
from panoptic.core.databases.sqlite_reader import SQLiteReader
from panoptic.models.data import (
    Commit, FileSource, Folder, File, Instance,
    Property, Tag, InstanceValue, Sha1Value, FileValue
)


class DataReader(SQLiteReader):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_max_commit_id(self) -> int:
        result = self.conn.execute(f"SELECT COALESCE(MAX(id), 0) FROM {COMMITS_SCHEMA.table}").fetchone()
        return result[0] if result else 0

    def get_next_sequence(self) -> int:
        result = self.conn.execute("SELECT COALESCE(MAX(id), 0) FROM sequence").fetchone()
        return result[0] if result else 0

    def get_commits_since(self, last_commit_id: int) -> List[Commit]:
        sql = f"SELECT * FROM {COMMITS_SCHEMA.table} WHERE id > ? ORDER BY id ASC"
        rows = self.conn.execute(sql, (last_commit_id,)).fetchall()
        return [COMMITS_SCHEMA._decode_row(r) for r in rows]

    def get_commits(self, offset: int = None, limit: int = None, group_id: int = None) -> List[Commit]:
        sql = f"SELECT * FROM {COMMITS_SCHEMA.table}"
        params = []

        if group_id is not None:
            sql += " WHERE group_id = ?"
            params.append(group_id)

        sql += " ORDER BY id DESC"
        if limit is not None:
            sql += f" LIMIT {limit}"
        if offset is not None:
            sql += f" OFFSET {offset}"

        rows = self.conn.execute(sql, params).fetchall()
        return [COMMITS_SCHEMA._decode_row(r) for r in rows]

    def get_commit_by_id(self, commit_id: int) -> Commit:
        return COMMITS_SCHEMA.get(self.conn, id=commit_id)[0]

    def get_file_sources(self, **filters) -> List[FileSource]:
        return FILE_SOURCES_SCHEMA.get(self.conn, **filters)

    def get_folders(self, **filters) -> List[Folder]:
        return FOLDERS_SCHEMA.get(self.conn, **filters)

    def get_files(self, **filters) -> List[File]:
        return FILES_SCHEMA.get(self.conn, **filters)

    def get_instances(self, **filters) -> List[Instance]:
        return INSTANCES_SCHEMA.get(self.conn, **filters)

    def get_properties(self, **filters) -> List[Property]:
        return PROPERTIES_SCHEMA.get(self.conn, **filters)

    def get_tags(self, **filters) -> List[Tag]:
        return TAGS_SCHEMA.get(self.conn, **filters)

    def get_instance_values(self, **filters) -> List[InstanceValue]:
        return INSTANCE_VALUES_SCHEMA.get(self.conn, **filters)

    def get_sha1_values(self, **filters) -> List[Sha1Value]:
        return SHA1_VALUES_SCHEMA.get(self.conn, **filters)

    def get_file_values(self, **filters) -> List[FileValue]:
        return FILE_VALUES_SCHEMA.get(self.conn, **filters)

    def count_instance_values(self) -> int:
        return self.conn.execute(f"SELECT COUNT(*) FROM {INSTANCE_VALUES_SCHEMA.table}").fetchone()[0]

    def count_sha1_values(self) -> int:
        return self.conn.execute(f"SELECT COUNT(*) FROM {SHA1_VALUES_SCHEMA.table}").fetchone()[0]

    def count_file_values(self) -> int:
        return self.conn.execute(f"SELECT COUNT(*) FROM {FILE_VALUES_SCHEMA.table}").fetchone()[0]

    def iter_instance_values(self, batch_size: int):
        cursor = self.conn.execute(f"SELECT * FROM {INSTANCE_VALUES_SCHEMA.table}")
        while rows := cursor.fetchmany(batch_size):
            yield [INSTANCE_VALUES_SCHEMA._decode_row(r) for r in rows]

    def iter_sha1_values(self, batch_size: int):
        cursor = self.conn.execute(f"SELECT * FROM {SHA1_VALUES_SCHEMA.table}")
        while rows := cursor.fetchmany(batch_size):
            yield [SHA1_VALUES_SCHEMA._decode_row(r) for r in rows]

    def iter_file_values(self, batch_size: int):
        cursor = self.conn.execute(f"SELECT * FROM {FILE_VALUES_SCHEMA.table}")
        while rows := cursor.fetchmany(batch_size):
            yield [FILE_VALUES_SCHEMA._decode_row(r) for r in rows]

    def get_delta(self, since: int) -> dict:
        data = {
            'instances':       INSTANCES_SCHEMA.get_since(self.conn, since),
            'files':           FILES_SCHEMA.get_since(self.conn, since),
            'folders':         FOLDERS_SCHEMA.get_since(self.conn, since),
            'properties':      PROPERTIES_SCHEMA.get_since(self.conn, since),
            'tags':            TAGS_SCHEMA.get_since(self.conn, since),
            'instance_values': INSTANCE_VALUES_SCHEMA.get_since(self.conn, since),
            'image_values':    SHA1_VALUES_SCHEMA.get_since(self.conn, since),
            'file_values':     FILE_VALUES_SCHEMA.get_since(self.conn, since),
        }
        max_seq = since
        for table in ('instances', 'files', 'folders', 'properties', 'tags',
                      'instance_values', 'sha1_values', 'file_values'):
            row = self.conn.execute(
                f"SELECT MAX(sequence) FROM {table} WHERE sequence > ?", (since,)
            ).fetchone()
            if row and row[0] is not None:
                max_seq = max(max_seq, row[0])
        data['sequence'] = max_seq
        return data