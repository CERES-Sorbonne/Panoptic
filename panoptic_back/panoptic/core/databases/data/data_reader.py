import json
from typing import List, Type, TypeVar, Any

import msgspec

from panoptic.core.databases.data.create import COMMITS_SCHEMA, FILE_SOURCES_SCHEMA, FOLDERS_SCHEMA, FILES_SCHEMA, \
    INSTANCES_SCHEMA, PROPERTIES_SCHEMA, TAGS_SCHEMA, INSTANCE_VALUES_SCHEMA, SHA1_VALUES_SCHEMA
from panoptic.core.databases.sqlite_reader import SQLiteReader
from panoptic.models.data import (
    Commit, FileSource, Folder, File, Instance,
    Property, Tag, InstanceValue, Sha1Value
)

T = TypeVar("T", bound=msgspec.Struct)


class DataReader(SQLiteReader):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._schema_lookup = {
            Commit: COMMITS_SCHEMA,
            FileSource: FILE_SOURCES_SCHEMA,
            Folder: FOLDERS_SCHEMA,
            File: FILES_SCHEMA,
            Instance: INSTANCES_SCHEMA,
            Property: PROPERTIES_SCHEMA,
            Tag: TAGS_SCHEMA,
            InstanceValue: INSTANCE_VALUES_SCHEMA,
            Sha1Value: SHA1_VALUES_SCHEMA,
        }

    def _fetch_entities(self, model_type: Type[T], **filters) -> List[T]:
        """Generic fetcher using the EntitySchema build logic."""
        schema = self._schema_lookup[model_type]
        sql, params = schema.build_get_sql(**filters)

        # We use fetch_structs if your base class supports params,
        # otherwise we execute and convert manually.
        return self.fetch_structs(sql, model_type, params)

    # --- Specialized Methods ---

    def get_max_commit_id(self) -> int:
        schema = self._schema_lookup[Commit]
        sql = f"SELECT COALESCE(MAX(id), 0) FROM {schema.table}"
        result = self.fetch_all(sql)
        return result[0][0] if result else 0

    def get_commits(self, offset: int = None, limit: int = None, group_id: int = None) -> List[Commit]:
        schema = self._schema_lookup[Commit]
        # Use schema logic but append ordering/pagination
        filters = {"group_id": group_id} if group_id is not None else {}
        sql, params = schema.build_get_sql(**filters)

        sql += " ORDER BY id DESC"
        if limit is not None: sql += f" LIMIT {limit}"
        if offset is not None: sql += f" OFFSET {offset}"

        return self.fetch_structs(sql, Commit, params)

    def get_commit_by_id(self, commit_id: int):
        return self._fetch_entities(Commit, id=commit_id)[0]

    # --- Boilerplate-free methods ---

    def get_file_sources(self, **filters) -> List[FileSource]:
        return self._fetch_entities(FileSource, **filters)

    def get_folders(self, **filters) -> List[Folder]:
        return self._fetch_entities(Folder, **filters)

    def get_files(self, **filters) -> List[File]:
        return self._fetch_entities(File, **filters)

    def get_instances(self, **filters) -> List[Instance]:
        return self._fetch_entities(Instance, **filters)

    def get_properties(self, **filters) -> List[Property]:
        return self._fetch_entities(Property, **filters)

    def get_tags(self, **filters) -> List[Tag]:
        return self._fetch_entities(Tag, **filters)

    def get_instance_values(self, **filters) -> List[InstanceValue]:
        return self._fetch_entities(InstanceValue, **filters)

    def get_sha1_values(self, **filters) -> List[Sha1Value]:
        return self._fetch_entities(Sha1Value, **filters)