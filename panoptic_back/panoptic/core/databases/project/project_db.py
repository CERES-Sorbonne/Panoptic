import logging
from pathlib import Path
from typing import Union, List, TypeVar, Optional

# From your provided snippets
from panoptic.core.databases.project.create import (
    project_db_desc,
    ID_REGISTRY_SHEMA,  # The KeyValueSchema instance
    TAB_DATA_SCHEMA,
    PLUGIN_DATA_SCHEMA,
    USER_DEFAULTS_SCHEMA
)
from panoptic.core.databases.project.models import TabData, PluginData, UserDefaults
from panoptic.core.databases.sqlite_db import SQLiteWriter
from panoptic.models import Tag, Property, Instance
from panoptic.models.data import File, Folder, FileSource, Commit
from panoptic.core.databases.media.models import ImageType, VectorType, Map

T = TypeVar("T")


class ProjectDB(SQLiteWriter):
    def __init__(self, path: str | Path):
        super().__init__(path, description=project_db_desc)

    def start(self):
        super().start()
        # Initialize the registry table using the Schema helper
        with self.transaction() as tx:
            ID_REGISTRY_SHEMA.ensure_keys(tx)
        logging.info("ProjectDB registry initialized.")

    def allocate(self, key: str, number: int = 1) -> Union[int, range]:
        """
        Generic allocation logic using ID_REGISTRY_SHEMA.
        Returns a single int if number=1, or a range if number > 1.
        """
        # ID_REGISTRY_SHEMA._field_names contains ['files', 'folders', etc.]
        if key not in ID_REGISTRY_SHEMA._field_names:
            raise ValueError(f"Key '{key}' is not a valid registry key.")

        with self.transaction() as tx:
            # 1. Get current ID (KeyValueSchema handles JSON loads and defaults)
            current_id = ID_REGISTRY_SHEMA.get_key(tx, key)

            # 2. Calculate next boundary
            next_id = current_id + number

            # 3. Save back (KeyValueSchema handles JSON dumps and upsert)
            ID_REGISTRY_SHEMA.set_key(tx, key, next_id)

            if number > 1:
                return range(current_id, next_id)
            return current_id

    def _handle_allocation(self, key: str, items_or_n: Union[List[T], int]) -> Union[int, range, List[T]]:
        """Polymorphic helper to support Registry-style (int) or List-style (objects)."""
        if isinstance(items_or_n, int):
            return self.allocate(key, items_or_n)

        n = len(items_or_n)
        if n == 0:
            return items_or_n

        ids = self.allocate(key, n)
        # Ensure we have an iterable for zip (range is already iterable)
        id_iter = ids if isinstance(ids, range) else [ids]

        for obj, id_val in zip(items_or_n, id_iter):
            obj.id = id_val

        return items_or_n

    # --- Allocation Wrappers ---

    def allocate_commits(self, val: Union[List[Commit], int] = 1):
        return self._handle_allocation('commits', val)

    def allocate_file_sources(self, val: Union[List[FileSource], int] = 1):
        return self._handle_allocation('file_sources', val)

    def allocate_folders(self, val: Union[List[Folder], int] = 1):
        return self._handle_allocation('folders', val)

    def allocate_files(self, val: Union[List[File], int] = 1):
        return self._handle_allocation('files', val)

    def allocate_instances(self, val: Union[List[Instance], int] = 1):
        return self._handle_allocation('instances', val)

    def allocate_properties(self, val: Union[List[Property], int] = 1):
        return self._handle_allocation('properties', val)

    def allocate_tags(self, val: Union[List[Tag], int] = 1):
        return self._handle_allocation('tags', val)

    def allocate_maps(self, val: Union[List[Map], int] = 1):
        return self._handle_allocation('maps', val)

    def allocate_vector_types(self, val: Union[List[VectorType], int] = 1):
        return self._handle_allocation('vector_types', val)

    def allocate_image_types(self, val: Union[List[ImageType], int] = 1):
        return self._handle_allocation('image_types', val)

    # --- Data Access Methods ---

    def set_tab_data(self, tab: TabData):
        with self.transaction() as tx:
            TAB_DATA_SCHEMA.upsert(tx, tab)

    def get_tab_data(self, tab_id: str) -> Optional[TabData]:
        rows = TAB_DATA_SCHEMA.get(self.conn, id=tab_id)
        return rows[0] if rows else None

    def get_user_tabs(self, user_id: str) -> List[TabData]:
        return TAB_DATA_SCHEMA.get(self.conn, user_id=user_id)

    def set_plugin_data(self, data: PluginData):
        with self.transaction() as tx:
            PLUGIN_DATA_SCHEMA.upsert(tx, data)

    def get_plugin_data(self, plugin_id: int, key: str) -> Optional[PluginData]:
        rows = PLUGIN_DATA_SCHEMA.get(self.conn, plugin_id=plugin_id, key=key)
        return rows[0] if rows else None

    def set_user_defaults(self, defaults: UserDefaults):
        with self.transaction() as tx:
            USER_DEFAULTS_SCHEMA.upsert(tx, defaults)

    def get_user_defaults(self, user_id: str, key: str) -> Optional[UserDefaults]:
        rows = USER_DEFAULTS_SCHEMA.get(self.conn, user_id=user_id, key=key)
        return rows[0] if rows else None