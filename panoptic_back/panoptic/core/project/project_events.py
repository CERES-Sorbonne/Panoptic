from typing import Callable, Awaitable

from panoptic.models import Instance, DeleteFolderConfirm, DbUpdate, ProjectState, SyncData, DbCommit, Folder, \
    PropertyGroup, VectorType, TaskState, ProjectSettings
from panoptic.utils import EventListener


class ImportInstanceEvent(EventListener):
    def register(self, callback: Callable[[Instance], Awaitable[None]]):
        super().register(callback)

    def emit(self, event: Instance):
        super().emit(event)


class DeletedFolderEvent(EventListener):
    def register(self, callback: Callable[[DeleteFolderConfirm], Awaitable[None]]):
        super().register(callback)

    def emit(self, event: DeleteFolderConfirm):
        super().emit(event)


class DbUpdateEvent(EventListener):
    def register(self, callback: Callable[[DbUpdate], Awaitable[None]]):
        super().register(callback)

    def emit(self, event: DbUpdate):
        super().emit(event)


class SyncEvent(EventListener):
    def __init__(self, project_id: int):
        super().__init__()
        self.project_id = project_id

    def emitProjectState(self, state: ProjectState):
        self._emit('project_state', state)

    def emitCommit(self, commit: DbCommit):
        self._emit('commit', commit)

    def emitFolders(self, folders: list[Folder]):
        self._emit('folders', folders)

    def emitFoldersDelete(self):
        self._emit('folders_delete', True)

    def emitSettings(self, settings: ProjectSettings):
        self._emit('project_settings', settings)

    def emitVectorTypes(self, types: list[VectorType]):
        self._emit('vector_types', types)

    def emitTasks(self, tasks: list[TaskState]):
        self._emit('tasks', tasks)

    def emit(self, data: SyncData):
        super().emit(data)

    def _emit(self, key: str, data):
        self.emit(SyncData(key=key, project_id=self.project_id, data=data))


class ProjectEvents:
    def __init__(self, project_id: int):
        self.import_instance = ImportInstanceEvent()
        self.delete_folder = DeletedFolderEvent()
        self.sync = SyncEvent(project_id=project_id)
