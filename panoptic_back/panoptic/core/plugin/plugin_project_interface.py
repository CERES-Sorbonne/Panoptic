from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Awaitable

from panoptic.core.task.task import Task

if TYPE_CHECKING:
    from panoptic.core.project.project import Project
    from panoptic.core.plugin.plugin import APlugin

from panoptic.models import ImagePropertyKey, InstanceProperty, PropertyType, PropertyMode, Property, \
    DbCommit, Vector, Instance, DeleteFolderConfirm, VectorType


class PluginProjectInterface:
    def __init__(self, project: Project, plugin: APlugin):
        self._project = project
        self.ui = project.ui
        self._plugin = plugin
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
        return await self._project.db.get_instance_property_values(property_ids, instance_ids)

    async def get_instance_property_values_from_keys(self, keys: list[InstanceProperty]):
        return await self._project.db.get_instance_property_values_from_keys(keys)

    async def get_image_property_values(self, property_ids: list[int] = None, sha1s: list[str] = None):
        return await self._project.db.get_image_property_values(property_ids, sha1s)

    async def get_image_property_values_from_keys(self, keys: list[ImagePropertyKey]):
        return await self._project.db.get_image_property_values_from_keys(keys)

    async def get_vectors(self, type_id: int, sha1s: list[str] = None):
        return await self._project.db.get_vectors(type_id, sha1s)

    async def get_vector_types(self, source: str = None):
        return await self._project.db.get_vector_types(source=source)

    async def vector_exist(self, type_id: int, sha1: str) -> bool:
        return await self._project.db.vector_exist(type_id, sha1)

    # CREATE

    def create_instance(self, folder_id: int, name: str, extension: str, sha1: str, url: str, width: int,
                        height: int, ahash: str):
        return self._project.db.create_instance(folder_id=folder_id, name=name, extension=extension, sha1=sha1, url=url,
                                                height=height, width=width, ahash=ahash)

    def create_property(self, name: str, type_: PropertyType, mode: PropertyMode) -> Property:
        return self._project.db.create_property(name, type_, mode)

    async def get_or_create_property(self, property_name: str, property_type: PropertyType = None,
                                     property_mode: PropertyMode = None):
        """
        Get an existing property or create a new one if it doesn't exist.

        @property_name: Name of the property to find or create
        @property_type: Type of property (required if creating new)
        @property_mode: Mode of property (required if creating new)
        @return: The existing or newly created Property
        """
        properties = await self.get_properties()

        # Search for existing property
        for prop in properties:
            if prop.name == property_name:
                # If type and mode are specified, ensure they match
                if property_type is not None and prop.type != property_type:
                    continue
                if property_mode is not None and prop.mode != property_mode:
                    continue
                return prop

        # Property not found, create new one
        if property_type is None or property_mode is None:
            raise ValueError(
                f"No existing property found with name '{property_name}' and no property_type "
                "and property_mode provided to create one"
            )

        new_prop = self.create_property(property_name, property_type, property_mode)
        return new_prop

    def create_tag(self, property_id: int, value: str, parent_ids: list[int] = None, color=-1):
        return self._project.db.create_tag(property_id, value, parent_ids, color)

    def create_vector_type(self, params: dict):
        return self._project.db.create_vector_type(self._plugin.name, params)

    async def add_vector_type(self, vec: VectorType):
        res = await self._project.db.add_vector_type(vec)
        return res


    # COMMIT

    async def apply_commit(self, commit: DbCommit):
        return await self._project.db.apply_commit(commit)

    async def do(self, commit: DbCommit):
        return await self._project.db.undo_queue.do(commit)

    async def undo(self):
        return await self._project.db.undo_queue.undo()

    async def redo(self):
        return await self._project.db.undo_queue.redo()

    async def add_vector(self, vector: Vector):
        res = await self._project.db.add_vector(vector)


    # TASKS
    def add_task(self, task: Task):
        self._project.task_queue.add_task(task)

    async def run_async(self, function, *args):
        return await self._project.run_async(function, *args)

    # EVENTS
    def on_instance_import(self, callback: Callable[[Instance], Awaitable[None]]):
        return self._project.on.import_instance.register(callback)

    def on_folder_delete(self, callback: Callable[[DeleteFolderConfirm], Awaitable[None]]):
        return self._project.on.delete_folder.register(callback)


