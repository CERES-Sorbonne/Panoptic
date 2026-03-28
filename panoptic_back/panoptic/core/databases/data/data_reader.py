import json
from typing import List

import msgspec
from pypika import Query, Table, Order, functions as fn
from pypika.queries import QueryBuilder

from panoptic.core.databases.sqlite_reader import SQLiteReader
from panoptic.models.data import Commit, FileSource, Folder, File, Instance, Property, Tag, InstanceValue, Sha1Value

# Schema Tables
COMMITS = Table('commits')
FILE_SOURCES = Table('file_sources')
FOLDERS = Table('folders')
FILES = Table('files')
INSTANCES = Table('instances')
PROPERTIES = Table('properties')
TAGS = Table('tags')
INSTANCE_VALUES = Table('instance_values')
SHA1_VALUES = Table('sha1_values')


def _filter_query(table: Table, **filters) -> QueryBuilder:
    """
    Helper to build Pypika queries from dictionary filters.
    It handles both single values and lists (using IN).
    """
    query = Query.from_(table).select('*')
    for col, values in filters.items():
        if values is not None:
            # Ensure values is a list for the .isin() operator
            if not isinstance(values, (list, tuple, set, range)):
                values = [values]
            query = query.where(getattr(table, col).isin(values))
    return query


class DataReader(SQLiteReader):

    def get_max_commit_id(self) -> int:
        query = Query.from_(COMMITS).select(
            fn.Coalesce(fn.Max(COMMITS.id), 0)
        )
        # Use fetch_all since we only want a single scalar value
        result = self.fetch_all(query.get_sql(quote_char=None))
        return result[0][0] if result else 0

    def get_commits(self, offset: int | None = None, limit: int | None = None, group_id: int | None = None) -> List[
        Commit]:
        query = Query.from_(COMMITS).select(
            COMMITS.id, COMMITS.group_id, COMMITS.source, COMMITS.timestamp
        ).orderby(COMMITS.id, order=Order.desc)

        if group_id is not None:
            query = query.where(COMMITS.group_id == group_id)
        if limit is not None:
            query = query.limit(limit)
        if offset is not None:
            query = query.offset(offset)

        return self.fetch_structs(query.get_sql(quote_char=None), Commit)

    def get_file_sources(self, **filters) -> List[FileSource]:
        query = _filter_query(FILE_SOURCES, **filters)
        return self.fetch_structs(query.get_sql(quote_char=None), FileSource)

    def get_folders(self, **filters) -> List[Folder]:
        query = _filter_query(FOLDERS, **filters)
        return self.fetch_structs(query.get_sql(quote_char=None), Folder)

    def get_files(self, **filters) -> List[File]:
        query = _filter_query(FILES, **filters)
        return self.fetch_structs(query.get_sql(quote_char=None), File)

    def get_instances(self, **filters) -> List[Instance]:
        query = _filter_query(INSTANCES, **filters)
        return self.fetch_structs(query.get_sql(quote_char=None), Instance)

    def get_properties(self, **filters) -> List[Property]:
        query = _filter_query(PROPERTIES, **filters)
        return self.fetch_structs(query.get_sql(quote_char=None), Property)

    def get_tags(self, **filters) -> List[Tag]:
        """Special handling for the JSON 'parents' column."""
        query = _filter_query(TAGS, **filters)
        if not self.is_loaded: self.start()

        cursor = self.conn.execute(query.get_sql(quote_char=None))
        results = []
        for row in cursor:
            # SQLite returns row as tuple. Convert to list to modify JSON field.
            row_data = list(row)
            # Assuming 'parents' is at index 2 based on your Tag struct definition
            if row_data[2]:
                row_data[2] = json.loads(row_data[2])
            else:
                row_data[2] = []

            results.append(msgspec.convert(row_data, type=Tag))
        return results

    def get_instance_values(self, **filters) -> List[InstanceValue]:
        query = _filter_query(INSTANCE_VALUES, **filters)
        return self.fetch_structs(query.get_sql(quote_char=None), InstanceValue)

    def get_sha1_values(self, **filters) -> List[Sha1Value]:
        query = _filter_query(SHA1_VALUES, **filters)
        print(query.get_sql())
        return self.fetch_structs(query.get_sql(quote_char=None), Sha1Value)