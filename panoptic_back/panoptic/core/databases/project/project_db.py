from pathlib import Path

from panoptic.core.databases.media.models import ImageType, VectorType, Map
from panoptic.core.databases.project.create import project_db_desc, ID_REGISTRY_SHEMA, TAB_DATA_SCHEMA, \
    PLUGIN_DATA_SCHEMA, USER_DEFAULTS_SCHEMA
from panoptic.core.databases.project.models import TabData, PluginData, UserDefaults
from panoptic.core.databases.sqlite_db import SQLiteWriter
from panoptic.models import Tag, Property, Instance
from panoptic.models.data import File, Folder, FileSource, Commit


class ProjectDB(SQLiteWriter):
    def __init__(self, path: str | Path):
        super().__init__(path, description=project_db_desc)

    def allocate(self, key: str, number: int = 1) -> int | range:
        if key not in ID_REGISTRY_SHEMA._field_names:
            raise ValueError(f"Key '{key}' is not a valid registry key.")
        with self.transaction() as tx:
            current_id = ID_REGISTRY_SHEMA.get_key(tx, key)
            next_id = current_id + number
            ID_REGISTRY_SHEMA.set_key(tx, key, next_id)
            return range(current_id, current_id + number)

    # --- Allocation Methods ---
    def allocate_commits(self, commits: list[Commit]) -> list[Commit]:
        if not commits:
            return commits

        n = len(commits)
        ids = self.allocate('commits', n)

        for commit, id_val in zip(commits, ids):
            commit.id = id_val

        return commits

    def allocate_file_sources(self, file_sources: list[FileSource]) -> list[FileSource]:
        if not file_sources:
            return file_sources

        n = len(file_sources)
        ids = self.allocate('file_sources', n)

        for source, id_val in zip(file_sources, ids):
            source.id = id_val

        return file_sources

    def allocate_folders(self, folders: list[Folder]) -> list[Folder]:
        if not folders:
            return folders

        n = len(folders)
        ids = self.allocate('folders', n)

        for folder, id_val in zip(folders, ids):
            folder.id = id_val

        return folders

    def allocate_files(self, files: list[File]) -> list[File]:
        if not files:
            return files

        n = len(files)
        ids = self.allocate('files', n)

        for file_obj, id_val in zip(files, ids):
            file_obj.id = id_val

        return files

    def allocate_instances(self, instances: list[Instance]) -> list[Instance]:
        if not instances:
            return instances

        n = len(instances)
        ids = self.allocate('instances', n)

        for instance, id_val in zip(instances, ids):
            instance.id = id_val

        return instances

    def allocate_properties(self, properties: list[Property]) -> list[Property]:
        if not properties:
            return properties

        n = len(properties)
        ids = self.allocate('properties', n)

        for prop, id_val in zip(properties, ids):
            prop.id = id_val

        return properties

    def allocate_tags(self, tags: list[Tag]) -> list[Tag]:
        if not tags:
            return tags

        n = len(tags)
        ids = self.allocate('tags', n)

        for tag, id_val in zip(tags, ids):
            tag.id = id_val

        return tags

    def allocate_maps(self, maps: list[Map]) -> list[Map]:
        if not maps:
            return maps

        n = len(maps)
        ids = self.allocate('maps', n)

        for map_obj, id_val in zip(maps, ids):
            map_obj.id = id_val

        return maps

    def allocate_vector_types(self, vector_types: list[VectorType]) -> list[VectorType]:
        if not vector_types:
            return vector_types

        n = len(vector_types)
        ids = self.allocate('vector_types', n)

        for v_type, id_val in zip(vector_types, ids):
            v_type.id = id_val

        return vector_types

    def allocate_image_types(self, image_types: list[ImageType]) -> list[ImageType]:
        if not image_types:
            return image_types

        n = len(image_types)
        ids = self.allocate('image_types', n)

        for i_type, id_val in zip(image_types, ids):
            i_type.id = id_val

        return image_types

    def set_tab_data(self, tab: TabData):
        TAB_DATA_SCHEMA.upsert(self.conn, tab)
        self.conn.commit()

    def get_tab_data(self, tab_id: str):
        return TAB_DATA_SCHEMA.get(self.conn, id=tab_id)[0]

    def get_user_tabs(self, user_id: str):
        return TAB_DATA_SCHEMA.get(self.conn, user_id=user_id)

    def set_plugin_data(self, data: PluginData):
        PLUGIN_DATA_SCHEMA.upsert(self.conn, data)
        self.conn.commit()

    def get_plugin_data(self, plugin_id: int, key: str):
        return PLUGIN_DATA_SCHEMA.get(self.conn, plugin_id=plugin_id, key=key)[0]

    def get_all_plugin_data(self, plugin_id: int):
        return PLUGIN_DATA_SCHEMA.get(self.conn, plugin_id=plugin_id)

    def set_user_defaults(self, defaults: UserDefaults):
        USER_DEFAULTS_SCHEMA.upsert(self.conn, defaults)
        self.conn.commit()

    def get_user_defaults(self, user_id: str, key: str):
        return USER_DEFAULTS_SCHEMA.get(self.conn, user_id=user_id, key=key)[0]

    def get_all_user_defaults(self, user_id: str):
        return USER_DEFAULTS_SCHEMA.get(self.conn, user_id=user_id)


# db = ProjectDB('./tmp.db')
# db.start()
# db.set_tab_data(TabData(id="lala", user_id="me", state={'test': 1}, selection=None))
# print(db.get_user_tabs(user_id='me'))
# print(db.get_tab_data(tab_id="lala"))

