import logging
import sqlite3
import threading
from pathlib import Path
from typing import Callable, List, Optional, Union

from panoptic.core.databases.data.data_reader import DataReader
from panoptic.core.databases.data.data_writer import DataWriter
from panoptic.core.databases.media.create import datastore_desc
from panoptic.core.databases.media.media_db import MediaDB
from panoptic.core.databases.media.models import ImageAtlas, ImageType, Image, Map, Vector, VectorType
from panoptic.core.databases.panoptic.models import PluginKey
from panoptic.core.databases.project.models import ProjectConfig, TabData, UserDefaults
from panoptic.core.databases.project.project_db import ProjectDB
from panoptic.core.databases.data.models import (
    Commit, DataCommit, DeleteCommit, File, FileSource, FileValue, Folder, Instance,
    InstanceTagValue, InstanceValue, Property, Sha1TagValue, Sha1Value, Tag, UpsertCommit,
)
from panoptic.core.databases.entity_schema import OP_CREATE
from panoptic.core.databases.data.system_properties import SYSTEM_PROPERTIES, SYSTEM_PROPERTY_MAP
from panoptic.core.plugin.action_registry import ActionRegistry
from panoptic.core.task.task import Task
from panoptic.core.task.task_manager import TaskManager
from panoptic.core.importer.importer import Importer
from panoptic.core.exporter import Exporter


class Project:
    def __init__(self, folder: Path, plugin_keys: list[PluginKey] = None, on_update: Callable = None):
        self.folder           = Path(folder)
        self.project_db_path  = self.folder / 'project.db'
        self.data_db_path     = self.folder / 'data.db'
        self.media_db_path    = self.folder / 'media.db'

        self.config: ProjectConfig = ProjectConfig()
        self.task_manager = TaskManager(on_update=on_update)
        self.action       = ActionRegistry()
        self.plugins: list = []   # list[APlugin] — typed loosely to avoid circular import
        self.importer     = Importer(self)
        self.exporter     = Exporter(self)

        self._plugin_keys = plugin_keys or []

        # Persistent media DB — opened once in start(), closed in close()
        # Used for writes; reads use thread-local connections via _media_read_conn()
        self._media: MediaDB | None = None
        # Thread-local lightweight read connections for hot-path image reads
        self._media_read_local = threading.local()
        # In-memory image type cache — loaded on start(), refreshed on every write
        self._image_types: list[ImageType] = []

        # Event callback lists
        self._on_instance_import_callbacks: list[Callable] = []
        self._on_folder_delete_callbacks:   list[Callable] = []
        self._on_commit: Optional[Callable[[], None]] = None

        self._local_fs_id: int | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        self.folder.mkdir(parents=True, exist_ok=True)
        with ProjectDB(self.project_db_path) as db:
            self.config = db.config
        with DataWriter(str(self.data_db_path)) as _:
            pass  # seeds data.db schema
        self._media = MediaDB(str(self.media_db_path), datastore_desc)
        self._media.start()
        self._ensure_default_image_types()
        self._image_types = self._media.get_image_types()
        self._ensure_system_properties()
        self._ensure_local_file_source()
        if self._plugin_keys:
            from panoptic.core.plugin.load_plugin_task import LoadPluginTask
            self.task_manager.add_task(LoadPluginTask(self, self._plugin_keys))

    def _ensure_default_image_types(self):
        existing = self._media.get_image_types()
        if not existing:
            # New project: create defaults through the allocator so the counter
            # advances to the correct value automatically.
            defaults = [
                ImageType(id=0, name='small', format='jpeg', width=256,  height=256,  auto_gen=True),
                ImageType(id=0, name='large', format='jpeg', width=1024, height=1024, auto_gen=True),
            ]
            self.allocate_image_types(defaults)
            for t in defaults:
                self._media.upsert_image_type(t)
        else:
            # Existing project: sync the counter past the highest existing ID so
            # future allocations never collide with already-used IDs.
            max_id = max(t.id for t in existing)
            with ProjectDB(self.project_db_path) as db:
                current = db.allocate('image_types', 0)  # peek without advancing
                if current <= max_id:
                    db.allocate('image_types', max_id + 1 - current)

    def _ensure_system_properties(self):
        existing = {p.system_key: p for p in self.get_properties() if p.system_key}

        # Insert missing system properties
        needed = [sp for sp in SYSTEM_PROPERTIES if sp.key not in existing]
        if needed:
            ids = self.allocate_properties(len(needed))
            if isinstance(ids, int):
                ids = range(ids, ids + 1)
            commit = UpsertCommit()
            for sp, prop_id in zip(needed, ids):
                commit.properties[prop_id] = Property(
                    id=prop_id, dtype=sp.dtype, mode=sp.mode, name=sp.key,
                    access='read', tag_list_id=None, system_key=sp.key,
                    commit_id=0, operation=OP_CREATE,
                )
            self.apply_upsert_commit('system', commit)

        # Fix stale modes on already-existing system properties
        stale = [p for p in existing.values() if p.mode != SYSTEM_PROPERTY_MAP[p.system_key].mode]
        if stale:
            commit = UpsertCommit()
            for p in stale:
                commit.properties[p.id] = Property(
                    id=p.id, dtype=p.dtype, mode=SYSTEM_PROPERTY_MAP[p.system_key].mode, name=p.name,
                    access=p.access, tag_list_id=p.tag_list_id, system_key=p.system_key,
                    commit_id=0, operation=OP_CREATE,
                )
            self.apply_upsert_commit('system', commit)

    def _ensure_local_file_source(self):
        sources = self.get_file_sources()
        local = next((s for s in sources if s.dtype == 'local'), None)
        if local:
            self._local_fs_id = local.id
            return
        fs_id = self.allocate_file_sources(1)
        commit = UpsertCommit()
        commit.file_sources[fs_id] = FileSource(
            id=fs_id, dtype='local', name='local_filesystem', root_url=None,
        )
        self.apply_upsert_commit('system', commit)
        self._local_fs_id = fs_id

    @property
    def local_fs_id(self) -> int:
        return self._local_fs_id

    def close(self):
        self.task_manager.close()
        if self._media:
            self._media.close()
            self._media = None

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

    def _media_read_conn(self) -> sqlite3.Connection:
        """Return a thread-local read connection to media.db.

        Created once per thread on first use — just connect() + two PRAGMAs.
        No migration or schema setup needed since _media.start() already did that.
        """
        local = self._media_read_local
        if not hasattr(local, 'conn'):
            conn = sqlite3.connect(str(self.media_db_path), check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            local.conn = conn
        return local.conn

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

    def allocate_property_groups(self, val: int = 1):
        with self._project_db() as db:
            return db.allocate_property_groups(val)

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

    def get_property_groups(self, **filters):
        with self._data_reader() as r:
            return r.get_property_groups(**filters)

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

    def get_instance_tag_values(self, **filters) -> List[InstanceTagValue]:
        with self._data_reader() as r:
            return r.get_instance_tag_values(**filters)

    def get_sha1_tag_values(self, **filters) -> List[Sha1TagValue]:
        with self._data_reader() as r:
            return r.get_sha1_tag_values(**filters)

    def get_tag_counts(self, property_id: int | None = None) -> list[dict]:
        with self._data_reader() as r:
            return r.get_tag_counts(property_id=property_id)

    def count_instances_per_folder(self) -> dict[int, int]:
        with self._data_reader() as r:
            return r.count_instances_per_folder()

    # ------------------------------------------------------------------
    # Writes  (DataWriter open/close per call)
    # ------------------------------------------------------------------

    def apply_commit(self, source: str, commit: DataCommit, group_id: int = None) -> Commit:
        """Unified create/update/delete for the logged (revertable) entities."""
        with self._data_writer() as w:
            result = w.apply_commit(source, commit, group_id=group_id)
        self._fire_on_commit()
        return result

    def apply_upsert_commit(self, source: str, commit: UpsertCommit, group_id: int = None) -> Commit:
        with self._data_writer() as w:
            result = w.apply_upsert_commit(source, commit, group_id=group_id)
        self._fire_on_commit()
        return result

    def apply_delete_commit(self, source: str, commit: DeleteCommit, group_id: int = None) -> Commit:
        # Compat shim. Structural deletes here do not garbage-collect orphaned media (a
        # leftover blob is only wasted disk); callers that need media GC should use the
        # dedicated delete_instances/delete_folders/delete_file_sources API.
        with self._data_writer() as w:
            result = w.apply_delete_commit(source, commit, group_id=group_id)
        self._fire_on_commit()
        return result

    # ------------------------------------------------------------------
    # Structural deletes (hard delete + media GC + frontend reload signal)
    # ------------------------------------------------------------------

    def delete_instances(self, instance_ids: list[int]) -> dict:
        return self._structural_delete(lambda w: w.delete_instances(instance_ids))

    def delete_folders(self, folder_ids: list[int]) -> dict:
        return self._structural_delete(lambda w: w.delete_folders(folder_ids))

    def delete_file_sources(self, source_ids: list[int]) -> dict:
        return self._structural_delete(lambda w: w.delete_file_sources(source_ids))

    def _structural_delete(self, fn) -> dict:
        with self._data_writer() as w:
            result = fn(w)
        orphan_sha1s = result.get('orphan_sha1s') if result else None
        if orphan_sha1s and self._media:
            self._media.delete_media_for_sha1s(orphan_sha1s)
        self._fire_on_commit()
        return result

    def set_commit_active(self, commit_id: int, active: bool):
        with self._data_writer() as w:
            w.set_commit_active(commit_id, active)
        self._fire_on_commit()

    def _fire_on_commit(self) -> None:
        if self._on_commit:
            try:
                self._on_commit()
            except Exception:
                logging.exception("Project: error in _on_commit")

    # ------------------------------------------------------------------
    # Media  (all use the persistent self._media connection)
    # ------------------------------------------------------------------

    def get_image_types(self, **filters) -> List[ImageType]:
        if not filters:
            return self._image_types
        return self._media.get_image_types(**filters)

    def get_image_stats(self) -> dict:
        counts = self._media.get_image_stats()
        with self._data_reader() as r:
            row = r.conn.execute("SELECT COUNT(DISTINCT sha1) FROM instances").fetchone()
            sha1_count = row[0] if row else 0
        return {'counts': counts, 'sha1_count': sha1_count}

    def upsert_image_type(self, image_type: ImageType):
        self._media.upsert_image_type(image_type)
        self._image_types = self._media.get_image_types()

    def delete_image_type(self, image_type_id: int):
        self._media.delete_image_type(image_type_id)
        self._image_types = self._media.get_image_types()

    def get_file_path_for_sha1(self, sha1: str) -> str | None:
        with self._data_reader() as r:
            return r.get_file_path_for_sha1(sha1)

    def get_images(self, **filters) -> List[Image]:
        return self._media.get_images(**filters)

    def get_best_image_bytes(self, sha1: str, size: int | None) -> bytes | None:
        """Return thumbnail bytes for sha1 using cached type selection.

        size=None → largest stored type.
        size=N   → smallest type whose max dimension >= N; falls back to largest.
        """
        types = self._image_types
        if not types:
            return None
        sized = [(t.id, t.width or 0, t.height or 0) for t in types if t.width or t.height]
        if not sized:
            type_id = types[0].id
        elif size is None:
            type_id = max(sized, key=lambda t: max(t[1], t[2]))[0]
        else:
            candidates = [t for t in sized if max(t[1], t[2]) >= size]
            type_id = (
                min(candidates, key=lambda t: max(t[1], t[2]))[0]
                if candidates else
                max(sized, key=lambda t: max(t[1], t[2]))[0]
            )
        row = self._media_read_conn().execute(
            "SELECT data FROM images WHERE type_id=? AND sha1=?", (type_id, sha1)
        ).fetchone()
        return row[0] if row else None

    def upsert_images(self, images: List[Image]):
        self._media.upsert_images(images)

    def delete_image(self, type_id: int, sha1: str):
        self._media.delete_image(type_id, sha1)

    def get_vector_types(self, **filters) -> List[VectorType]:
        return self._media.get_vector_types(**filters)

    def upsert_vector_type(self, vector_type: VectorType):
        self._media.upsert_vector_type(vector_type)

    def delete_vector_type(self, vector_type_id: int):
        self._media.delete_vector_type(vector_type_id)

    def get_vector_stats(self) -> dict:
        stats = self._media.get_vector_stats()
        with self._data_reader() as r:
            row = r.conn.execute("SELECT COUNT(DISTINCT sha1) FROM instances").fetchone()
            stats['sha1_count'] = row[0] if row else 0
        return stats

    def get_vectors(self, **filters) -> List[Vector]:
        return self._media.get_vectors(**filters)

    def upsert_vectors(self, vectors: List[Vector]):
        self._media.upsert_vectors(vectors)

    def get_image_atlases(self, **filters) -> List[ImageAtlas]:
        return self._media.get_image_atlases(**filters)

    def upsert_image_atlas(self, atlas: ImageAtlas):
        self._media.upsert_image_atlas(atlas)

    def get_maps(self, **filters) -> List[Map]:
        return self._media.get_maps(**filters)

    def upsert_map(self, map_: Map):
        self._media.upsert_map(map_)

    def delete_map(self, map_id: int):
        self._media.delete_map(map_id)

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
        from panoptic.core.task.import_folder_task import ImportFolderTask
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
        from panoptic.core.plugin.plugin_interface import PluginProjectInterface
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
    # Events  (triggered by Project write methods)
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
