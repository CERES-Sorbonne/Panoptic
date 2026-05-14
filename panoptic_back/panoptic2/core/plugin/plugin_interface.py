"""PluginProjectInterface — safe sync wrapper over Project2 for plugin authors."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable, List

from panoptic.models.data import (
    Commit, File, FileSource, Folder, Instance, Property, Tag,
    InstanceValue, Sha1Value, UpsertCommit, DeleteCommit,
)
from panoptic2.core.task.task import Task

if TYPE_CHECKING:
    from panoptic2.core.project.project import Project2


class PluginProjectInterface:
    """Exposes a stable, curated API to plugin authors.

    Backed by Project2 — all methods are sync, connection-per-call.
    Plugin authors should use self.project (this interface), not self._project
    (the raw Project2).
    """

    def __init__(self, project: Project2):
        self._project = project

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_folders(self, **filters) -> List[Folder]:
        return self._project.get_folders(**filters)

    def get_files(self, **filters) -> List[File]:
        return self._project.get_files(**filters)

    def get_file_sources(self, **filters) -> List[FileSource]:
        return self._project.get_file_sources(**filters)

    def get_instances(self, **filters) -> List[Instance]:
        return self._project.get_instances(**filters)

    def get_properties(self, **filters) -> List[Property]:
        return self._project.get_properties(**filters)

    def get_tags(self, **filters) -> List[Tag]:
        return self._project.get_tags(**filters)

    def get_instance_values(self, **filters) -> List[InstanceValue]:
        return self._project.get_instance_values(**filters)

    def get_sha1_values(self, **filters) -> List[Sha1Value]:
        return self._project.get_sha1_values(**filters)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def apply_upsert_commit(self, source: str, commit: UpsertCommit, group_id: int = None) -> Commit:
        return self._project.apply_upsert_commit(source, commit, group_id=group_id)

    def apply_delete_commit(self, source: str, commit: DeleteCommit, group_id: int = None) -> Commit:
        return self._project.apply_delete_commit(source, commit, group_id=group_id)

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    def add_task(self, task: Task, high_priority: bool = False) -> Task:
        return self._project.add_task(task, high_priority=high_priority)

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def on_instance_import(self, callback: Callable[[List[Instance]], None]) -> None:
        self._project.on_instance_import(callback)

    def on_folder_delete(self, callback: Callable[[List[Folder]], None]) -> None:
        self._project.on_folder_delete(callback)

    # ------------------------------------------------------------------
    # Paths / misc
    # ------------------------------------------------------------------

    @property
    def base_path(self) -> Path:
        return self._project.folder
