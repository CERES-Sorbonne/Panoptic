from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Awaitable

from panoptic.core.task.task import Task

if TYPE_CHECKING:
    from panoptic.core.project.project import Project

from panoptic.models import ImagePropertyKey, InstanceProperty, PropertyType, PropertyMode, Property, \
    DbCommit, Vector, Instance


class PluginProjectInterface:
    def __init__(self, project: Project):
        self._project = project
        self.ui = project.ui

        self.base_path = project.base_path

    # GETTERS

    def get_project(self):
        return self._project

    async def get_folders(self):
        return await self._project.db.get_folders()

    async def get_instances(self, ids: list[int] = None, sha1s: list[str] = None):
        return await self._project.db.get_instances(ids, sha1s)

    async def get_properties(self, ids: list[int] = None, computed=False):
        return await self._project.db.get_properties(ids, computed)

    async def get_tags(self, ids: list[int] = None, property_ids: list[int] = None):
        return await self._project.db.get_tags2(ids, property_ids)

    async def get_instance_property_values(self, property_ids: list[int] = None, instance_ids: list[int] = None):
        return await self._project.db.get_raw_db().get_instance_property_values(property_ids, instance_ids)

    async def get_instance_property_values_from_keys(self, keys: list[InstanceProperty]):
        return await self._project.db.get_raw_db().get_instance_property_values_from_keys(keys)

    async def get_image_property_values(self, property_ids: list[int] = None, sha1s: list[str] = None):
        return await self._project.db.get_raw_db().get_image_property_values(property_ids, sha1s)

    async def get_image_property_values_from_keys(self, keys: list[ImagePropertyKey]):
        return await self._project.db.get_raw_db().get_image_property_values_from_keys(keys)

    async def get_vectors(self, source: str, vector_type: str, sha1s: list[str] = None):
        return await self._project.db.get_vectors(source, vector_type, sha1s)

    async def get_default_vectors(self, sha1s: list[str] = None):
        return await self._project.db.get_default_vectors(sha1s)

    async def vector_exist(self, source: str, type_: str, sha1: str) -> bool:
        return await self._project.db.vector_exist(source, type_, sha1)

    # CREATE

    def create_instance(self, folder_id: int, name: str, extension: str, sha1: str, url: str, width: int,
                        height: int, ahash: str):
        return self._project.db.create_instance(folder_id=folder_id, name=name, extension=extension, sha1=sha1, url=url,
                                                height=height, width=width, ahash=ahash)

    def create_property(self, name: str, type_: PropertyType, mode: PropertyMode) -> Property:
        return self._project.db.create_property(name, type_, mode)

    def create_tag(self, property_id: int, value: str, parent_ids: list[int] = None, color=-1):
        return self._project.db.create_tag(property_id, value, parent_ids, color)

    # COMMIT

    async def apply_commit(self, commit: DbCommit):
        return await self._project.db.apply_commit(commit)

    async def do(self, commit: DbCommit):
        return await self._project.undo_queue.do(commit)

    async def undo(self):
        return await self._project.undo_queue.undo()

    async def redo(self):
        return await self._project.undo_queue.redo()

    async def add_vector(self, vector: Vector):
        return await self._project.db.add_vector(vector)

    # TASKS
    def add_task(self, task: Task):
        self._project.task_queue.add_task(task)

    # EVENTS
    def on_instance_import(self, callback: Callable[[Instance], Awaitable[None]]):
        return self._project.on.import_instance.register(callback)
