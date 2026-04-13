from typing import List

from panoptic.core.databases.data.create import (
    COMMITS_SCHEMA, FILE_SOURCES_SCHEMA, FOLDERS_SCHEMA, FILES_SCHEMA,
    INSTANCES_SCHEMA, PROPERTIES_SCHEMA, TAGS_SCHEMA,
    INSTANCE_VALUES_SCHEMA, SHA1_VALUES_SCHEMA
)
from panoptic.core.databases.sqlite_reader import SQLiteReader
from panoptic.models.data import (
    Commit, FileSource, Folder, File, Instance,
    Property, Tag, InstanceValue, Sha1Value
)


class DataReader(SQLiteReader):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_max_commit_id(self) -> int:
        result = self.conn.execute(f"SELECT COALESCE(MAX(id), 0) FROM {COMMITS_SCHEMA.table}").fetchone()
        return result[0] if result else 0

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