"""PluginProjectInterface — self-contained project API for plugin authors.

Holds DB paths directly and opens its own connections per call.
No reference to Project is kept — plugins cannot reach internal project
state through this interface. Only what is explicitly exposed here is
accessible to plugin code.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, List

from panoptic.core.databases.data.data_reader import DataReader
from panoptic.core.databases.data.data_writer import DataWriter
from panoptic.core.databases.media.create import datastore_desc
from panoptic.core.databases.media.media_db import MediaDB
from panoptic.core.databases.media.models import Map, Vector, VectorType
from panoptic.core.databases.project.models import UserDefaults
from panoptic.core.databases.project.project_db import ProjectDB
from panoptic.core.databases.data.models import (
    Commit, DeleteCommit, File, FileSource, Folder, Instance, InstanceValue,
    Property, Sha1Value, Tag, UpsertCommit, FileValue,
)
from panoptic.core.plugin.action_registry import ActionRegistry, build_function_description
from panoptic.core.task.task import Task
from panoptic.models.action_models import FunctionDescription

if TYPE_CHECKING:
    from panoptic.core.task.task_manager import TaskManager


class PluginProjectInterface:
    def __init__(
        self,
        plugin_name: str,
        base_path: Path,
        data_db_path: Path,
        media_db_path: Path,
        project_db_path: Path,
        task_manager: TaskManager,
        action_registry: ActionRegistry,
        register_instance_import: Callable,
        register_folder_delete: Callable,
    ):
        self._name         = plugin_name
        self.base_path     = Path(base_path)
        self._data_path    = Path(data_db_path)
        self._media_path   = Path(media_db_path)
        self._project_path = Path(project_db_path)
        self._tasks        = task_manager
        self._actions      = action_registry
        self._reg_import   = register_instance_import
        self._reg_delete   = register_folder_delete

    # ------------------------------------------------------------------
    # Internal DB helpers — same open/close-per-call pattern as Project
    # ------------------------------------------------------------------

    def _data_reader(self) -> DataReader:
        return DataReader(str(self._data_path))

    def _data_writer(self) -> DataWriter:
        return DataWriter(str(self._data_path))

    def _media_db(self) -> MediaDB:
        return MediaDB(str(self._media_path), datastore_desc)

    def _project_db(self) -> ProjectDB:
        return ProjectDB(self._project_path)

    # ------------------------------------------------------------------
    # Read — data.db
    # ------------------------------------------------------------------

    def get_folders(self, **filters) -> List[Folder]:
        with self._data_reader() as r:
            return r.get_folders(**filters)

    def get_files(self, **filters) -> List[File]:
        with self._data_reader() as r:
            return r.get_files(**filters)

    def get_file_sources(self, **filters) -> List[FileSource]:
        with self._data_reader() as r:
            return r.get_file_sources(**filters)

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
    # Write — data.db  (source is always the plugin name)
    # ------------------------------------------------------------------

    def apply_upsert_commit(self, commit: UpsertCommit, group_id: int = None) -> Commit:
        with self._data_writer() as w:
            return w.apply_upsert_commit(self._name, commit, group_id=group_id)

    def apply_delete_commit(self, commit: DeleteCommit, group_id: int = None) -> Commit:
        with self._data_writer() as w:
            return w.apply_delete_commit(self._name, commit, group_id=group_id)

    # ------------------------------------------------------------------
    # Vectors — media.db
    # ------------------------------------------------------------------

    def get_vector_types(self, source: str = None) -> List[VectorType]:
        with self._media_db() as mdb:
            return mdb.get_vector_types(source=source) if source else mdb.get_vector_types()

    def upsert_vector_type(self, vt: VectorType) -> VectorType:
        """Insert or update a vector type. If vt.id < 0 a new ID is allocated."""
        if vt.id < 0:
            with self._project_db() as pdb:
                new_id = pdb.allocate_vector_types(1)
            vt = VectorType(id=new_id, source=vt.source, params=vt.params)
        with self._media_db() as mdb:
            mdb.upsert_vector_type(vt)
        return vt

    def delete_vector_type(self, type_id: int) -> None:
        with self._media_db() as mdb:
            mdb.delete_vector_type(type_id)

    def get_vectors(self, type_id: int, sha1s: List[str] = None) -> List[Vector]:
        filters = {'type_id': type_id}
        if sha1s is not None:
            filters['sha1'] = sha1s
        with self._media_db() as mdb:
            return mdb.get_vectors(**filters)

    def upsert_vectors(self, vectors: List[Vector]) -> None:
        with self._media_db() as mdb:
            mdb.upsert_vectors(vectors)

    def vector_exist(self, type_id: int, sha1: str) -> bool:
        with self._media_db() as mdb:
            return len(mdb.get_vectors(type_id=type_id, sha1=sha1)) > 0

    # ------------------------------------------------------------------
    # Maps — media.db
    # ------------------------------------------------------------------

    def get_maps(self, **filters) -> List[Map]:
        with self._media_db() as mdb:
            return mdb.get_maps(**filters)

    def upsert_map(self, map_: Map) -> Map:
        """Insert or update a map. If map_.id < 0 a new ID is allocated."""
        if map_.id < 0:
            with self._project_db() as pdb:
                new_id = pdb.allocate_maps(1)
            map_ = Map(
                id=new_id, source=map_.source, name=map_.name,
                key=map_.key, count=map_.count, data=map_.data,
            )
        with self._media_db() as mdb:
            mdb.upsert_map(map_)
        return map_

    def delete_map(self, map_id: int) -> None:
        with self._media_db() as mdb:
            mdb.delete_map(map_id)

    # ------------------------------------------------------------------
    # Plugin params — project.db  (namespaced to plugin name automatically)
    # ------------------------------------------------------------------

    def load_params(self) -> dict | None:
        with self._project_db() as db:
            row = db.get_user_defaults(user_id=f'plugin.{self._name}', key='params')
            return row.data if row else None

    def save_params(self, params: dict) -> None:
        with self._project_db() as db:
            db.set_user_defaults(UserDefaults(
                user_id=f'plugin.{self._name}',
                key='params',
                data=params,
            ))

    # ------------------------------------------------------------------
    # Action registration  (used by APlugin — not called directly)
    # ------------------------------------------------------------------

    def register_action(self, fn: Callable, hooks: list[str] = None) -> FunctionDescription:
        """Build a FunctionDescription and register fn in the project's ActionRegistry."""
        desc = build_function_description(self._name, fn, hooks)
        self._actions.add(fn, desc)
        return desc

    def register_action_with_desc(self, fn: Callable, description: FunctionDescription) -> None:
        """Register fn with an explicit FunctionDescription."""
        self._actions.add(fn, description)

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    def add_task(self, task: Task, high_priority: bool = False) -> Task:
        return self._tasks.add_task(task, high_priority=high_priority)

    # ------------------------------------------------------------------
    # CPU executor
    # ------------------------------------------------------------------

    def run_in_executor(self, fn: Callable, *args) -> Any:
        """Run a CPU-heavy function, blocking the caller until done.

        In panoptic2 routes and tasks are already running in threads, so
        this is a direct synchronous call. For GIL-releasing NumPy/sklearn
        work this is equivalent to the old asyncio run_async helper.
        """
        return fn(*args)

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def on_instance_import(self, callback: Callable[[List[Instance]], None]) -> None:
        self._reg_import(callback)

    def on_folder_delete(self, callback: Callable[[List[Folder]], None]) -> None:
        self._reg_delete(callback)
