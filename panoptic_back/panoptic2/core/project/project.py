from pathlib import Path
from typing import Callable, List, Optional, Union

from panoptic2.core.databases.data.data_reader import DataReader
from panoptic2.core.databases.data.data_writer import DataWriter
from panoptic2.core.databases.media.create import datastore_desc
from panoptic2.core.databases.media.media_db import MediaDB
from panoptic2.core.databases.media.models import ImageAtlas, ImageType, Image, Map, Vector, VectorType
from panoptic2.core.databases.panoptic.models import PluginKey
from panoptic2.core.databases.project.models import ProjectConfig, TabData, UserDefaults
from panoptic2.core.databases.project.project_db import ProjectDB
from panoptic2.core.databases.data.models import (
    Commit, DeleteCommit, File, FileSource, FileValue, Folder, Instance,
    InstanceValue, Property, Sha1Value, Tag, UpsertCommit,
)
from panoptic2.core.plugin.action_registry import ActionRegistry
from panoptic2.core.task.task import Task
from panoptic2.core.task.task_manager import TaskManager
from panoptic2.core.importer.importer import Importer2
from panoptic2.core.exporter import Exporter2


class Project2:
    def __init__(self, folder: Path, plugin_keys: list[PluginKey] = None, on_update: Callable = None):
        self.folder           = Path(folder)
        self.project_db_path  = self.folder / 'project.db'
        self.data_db_path     = self.folder / 'data.db'
        self.media_db_path    = self.folder / 'media.db'

        self.config: ProjectConfig = ProjectConfig()
        self.task_manager = TaskManager(on_update=on_update)
        self.action       = ActionRegistry()
        self.plugins: list = []   # list[APlugin] — typed loosely to avoid circular import
        self.importer     = Importer2(self)
        self.exporter     = Exporter2(self)

        self._plugin_keys = plugin_keys or []

        # Event callback lists
        self._on_instance_import_callbacks: list[Callable] = []
        self._on_folder_delete_callbacks:   list[Callable] = []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        self.folder.mkdir(parents=True, exist_ok=True)
        with ProjectDB(self.project_db_path) as db:
            self.config = db.config
        with DataWriter(str(self.data_db_path)) as _:
            pass  # seeds data.db schema
        with MediaDB(str(self.media_db_path), datastore_desc) as db:
            db.ensure_default_image_types()
        if self._plugin_keys:
            from panoptic2.core.plugin.load_plugin_task import LoadPluginTask
            self.task_manager.add_task(LoadPluginTask(self, self._plugin_keys))

    def close(self):
        self.task_manager.close()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _project_db(self) -> ProjectDB:
        return ProjectDB(self.project_db_path)

    def _data_reader(self) -> DataReader:
        return DataReader(str(self.data_db_path))

    def _data_writer(self) -> DataWriter:
        return DataWriter(str(self.data_db_path))

    def _media_db(self) -> MediaDB:
        return MediaDB(str(self.media_db_path), datastore_desc)

    # ------------------------------------------------------------------
    # Project config
    # ------------------------------------------------------------------

    def set_name(self, name: str):
        with self._project_db() as db:
            db.set_name(name)
            self.config = db.config

    # ------------------------------------------------------------------
    # ID allocation  (ProjectDB open/close per call)
    # ------------------------------------------------------------------

    def allocate_file_sources(self, val: Union[List[FileSource], int] = 1):
        with self._project_db() as db:
            return db.allocate_file_sources(val)

    def allocate_folders(self, val: Union[List[Folder], int] = 1):
        with self._project_db() as db:
            return db.allocate_folders(val)

    def allocate_files(self, val: Union[List[File], int] = 1):
        with self._project_db() as db:
            return db.allocate_files(val)

    def allocate_instances(self, val: Union[List[Instance], int] = 1):
        with self._project_db() as db:
            return db.allocate_instances(val)

    def allocate_properties(self, val: Union[List[Property], int] = 1):
        with self._project_db() as db:
            return db.allocate_properties(val)

    def allocate_tags(self, val: Union[List[Tag], int] = 1):
        with self._project_db() as db:
            return db.allocate_tags(val)

    def allocate_maps(self, val: Union[List[Map], int] = 1):
        with self._project_db() as db:
            return db.allocate_maps(val)

    def allocate_vector_types(self, val: Union[List[VectorType], int] = 1):
        with self._project_db() as db:
            return db.allocate_vector_types(val)

    def allocate_image_types(self, val: Union[List[ImageType], int] = 1):
        with self._project_db() as db:
            return db.allocate_image_types(val)

    # ------------------------------------------------------------------
    # Reads  (DataReader open/close per call)
    # ------------------------------------------------------------------

    def get_commits(self, **filters) -> List[Commit]:
        with self._data_reader() as r:
            return r.get_commits(**filters)

    def get_file_sources(self, **filters) -> List[FileSource]:
        with self._data_reader() as r:
            return r.get_file_sources(**filters)

    def get_folders(self, **filters) -> List[Folder]:
        with self._data_reader() as r:
            return r.get_folders(**filters)

    def get_files(self, **filters) -> List[File]:
        with self._data_reader() as r:
            return r.get_files(**filters)

    def get_instances(self, **filters) -> List[Instance]:
        with self._data_reader() as r:
            return r.get_instances(**filters)

    def get_properties(self, **filters) -> List[Property]:
        with self._data_reader() as r:
            return r.get_properties(**filters)

    def get_tags(self, **filters) -> List[Tag]:
        with self._data_reader() as r:
            return r.get_tags(**filters)

    def get_instance_values(self, **filters) -> List[InstanceValue]:
        with self._data_reader() as r:
            return r.get_instance_values(**filters)

    def get_sha1_values(self, **filters) -> List[Sha1Value]:
        with self._data_reader() as r:
            return r.get_sha1_values(**filters)

    def get_file_values(self, **filters) -> List[FileValue]:
        with self._data_reader() as r:
            return r.get_file_values(**filters)

    # ------------------------------------------------------------------
    # Writes  (DataWriter open/close per call)
    # ------------------------------------------------------------------

    def apply_upsert_commit(self, source: str, commit: UpsertCommit, group_id: int = None) -> Commit:
        with self._data_writer() as w:
            return w.apply_upsert_commit(source, commit, group_id=group_id)

    def apply_delete_commit(self, source: str, commit: DeleteCommit, group_id: int = None) -> Commit:
        with self._data_writer() as w:
            return w.apply_delete_commit(source, commit, group_id=group_id)

    def set_commit_active(self, commit_id: int, active: bool):
        with self._data_writer() as w:
            w.set_commit_active(commit_id, active)

    # ------------------------------------------------------------------
    # Media  (MediaDB open/close per call)
    # ------------------------------------------------------------------

    def get_image_types(self, **filters) -> List[ImageType]:
        with self._media_db() as db:
            return db.get_image_types(**filters)

    def get_image_stats(self) -> dict:
        with self._media_db() as db:
            counts = db.get_image_stats()
        with self._data_reader() as r:
            row = r.conn.execute("SELECT COUNT(DISTINCT sha1) FROM instances").fetchone()
            sha1_count = row[0] if row else 0
        return {'counts': counts, 'sha1_count': sha1_count}

    def upsert_image_type(self, image_type: ImageType):
        with self._media_db() as db:
            db.upsert_image_type(image_type)

    def delete_image_type(self, image_type_id: int):
        with self._media_db() as db:
            db.delete_image_type(image_type_id)

    def get_images(self, **filters) -> List[Image]:
        with self._media_db() as db:
            return db.get_images(**filters)

    def upsert_images(self, images: List[Image]):
        with self._media_db() as db:
            db.upsert_images(images)

    def delete_image(self, type_id: int, sha1: str):
        with self._media_db() as db:
            db.delete_image(type_id, sha1)

    def get_vector_types(self, **filters) -> List[VectorType]:
        with self._media_db() as db:
            return db.get_vector_types(**filters)

    def upsert_vector_type(self, vector_type: VectorType):
        with self._media_db() as db:
            db.upsert_vector_type(vector_type)

    def delete_vector_type(self, vector_type_id: int):
        with self._media_db() as db:
            db.delete_vector_type(vector_type_id)

    def get_vector_stats(self) -> dict:
        with self._media_db() as db:
            stats = db.get_vector_stats()
        with self._data_reader() as r:
            row = r.conn.execute("SELECT COUNT(DISTINCT sha1) FROM instances").fetchone()
            stats['sha1_count'] = row[0] if row else 0
        return stats

    def get_vectors(self, **filters) -> List[Vector]:
        with self._media_db() as db:
            return db.get_vectors(**filters)

    def upsert_vectors(self, vectors: List[Vector]):
        with self._media_db() as db:
            db.upsert_vectors(vectors)

    def get_image_atlases(self, **filters) -> List[ImageAtlas]:
        with self._media_db() as db:
            return db.get_image_atlases(**filters)

    def upsert_image_atlas(self, atlas: ImageAtlas):
        with self._media_db() as db:
            db.upsert_image_atlas(atlas)

    def get_maps(self, **filters) -> List[Map]:
        with self._media_db() as db:
            return db.get_maps(**filters)

    def upsert_map(self, map_: Map):
        with self._media_db() as db:
            db.upsert_map(map_)

    def delete_map(self, map_id: int):
        with self._media_db() as db:
            db.delete_map(map_id)

    # ------------------------------------------------------------------
    # UI state  (ProjectDB open/close per call)
    # ------------------------------------------------------------------

    def get_tab_data(self, tab_id: str) -> Optional[TabData]:
        with self._project_db() as db:
            return db.get_tab_data(tab_id)

    def set_tab_data(self, tab: TabData):
        with self._project_db() as db:
            db.set_tab_data(tab)

    def get_user_tabs(self, user_id: str) -> List[TabData]:
        with self._project_db() as db:
            return db.get_user_tabs(user_id)

    def delete_tab_data(self, tab_id: str):
        with self._project_db() as db:
            db.delete_tab_data(tab_id)

    def get_user_defaults(self, user_id: str, key: str) -> Optional[UserDefaults]:
        with self._project_db() as db:
            return db.get_user_defaults(user_id, key)

    def get_all_user_defaults(self, user_id: str) -> list[UserDefaults]:
        with self._project_db() as db:
            return db.get_all_user_defaults(user_id)

    def set_user_defaults(self, defaults: UserDefaults):
        with self._project_db() as db:
            db.set_user_defaults(defaults)

    def set_user_defaults_bulk(self, items: list[UserDefaults]):
        with self._project_db() as db:
            db.set_user_defaults_bulk(items)

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    def import_folder(self, path: str) -> Task:
        from panoptic2.core.task.import_folder_task import ImportFolderTask
        return self.add_task(ImportFolderTask(self, path))

    def add_task(self, task: Task, high_priority: bool = False) -> Task:
        return self.task_manager.add_task(task, high_priority=high_priority)

    def stop_task(self, task_id: str):
        self.task_manager.stop_task(task_id)

    def dismiss_task(self, task_id: str):
        self.task_manager.dismiss_task(task_id)

    def get_task_states(self):
        return self.task_manager.get_states()

    # ------------------------------------------------------------------
    # Plugins
    # ------------------------------------------------------------------

    def add_plugin(self, plugin) -> None:
        self.plugins.append(plugin)

    def make_plugin_interface(self, plugin_name: str):
        from panoptic2.core.plugin.plugin_interface import PluginProjectInterface
        return PluginProjectInterface(
            plugin_name=plugin_name,
            base_path=self.folder,
            data_db_path=self.data_db_path,
            media_db_path=self.media_db_path,
            project_db_path=self.project_db_path,
            task_manager=self.task_manager,
            action_registry=self.action,
            register_instance_import=self.on_instance_import,
            register_folder_delete=self.on_folder_delete,
        )

    def update_plugin_params(self, plugin_name: str, params: dict) -> None:
        plugin = next((p for p in self.plugins if p.name == plugin_name), None)
        if plugin is None:
            raise KeyError(f'Plugin {plugin_name!r} is not loaded')
        plugin.update_params(params)

    # ------------------------------------------------------------------
    # Events  (triggered by Project2 write methods)
    # ------------------------------------------------------------------

    def on_instance_import(self, callback: Callable) -> None:
        self._on_instance_import_callbacks.append(callback)

    def on_folder_delete(self, callback: Callable) -> None:
        self._on_folder_delete_callbacks.append(callback)

    def _trigger_instance_import(self, instances: list) -> None:
        for cb in self._on_instance_import_callbacks:
            try:
                cb(instances)
            except Exception:
                import logging
                logging.exception('on_instance_import callback failed')

    def _trigger_folder_delete(self, folders: list) -> None:
        for cb in self._on_folder_delete_callbacks:
            try:
                cb(folders)
            except Exception:
                import logging
                logging.exception('on_folder_delete callback failed')
