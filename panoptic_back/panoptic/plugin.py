"""Public API for Panoptic plugins: import everything a plugin needs from here.

    from panoptic.plugin import APlugin, Task, ActionContext, ActionResult, Instance

The older deep import paths (panoptic.core..., panoptic.models...) keep working.
"""
from panoptic.core.databases.data.models import (
    Commit, DataCommit, DeleteCommit, File, FileSource, FileValue, Folder, Instance,
    InstanceValue, Property, PropertyGroup, Sha1Value, Tag, UpsertCommit,
)
from panoptic.core.databases.media.models import Image, ImageType, Map, Vector, VectorType
from panoptic.core.plugin.plugin import APlugin
from panoptic.core.plugin.plugin_interface import PluginProjectInterface
from panoptic.core.task.task import Task, TaskCancelled
from panoptic.models.action_models import (
    ActionContext, ActionResult, FilePath, FolderPath, Group, InputFile, Notif, NotifType,
    OwnVectorType, PropertyId, Score, ScoreList,
)

__all__ = [
    # plugin, project access, tasks
    'APlugin', 'PluginProjectInterface', 'Task', 'TaskCancelled',
    # actions
    'ActionContext', 'ActionResult', 'Group', 'Score', 'ScoreList', 'Notif', 'NotifType',
    # action parameter markers
    'FilePath', 'FolderPath', 'InputFile', 'OwnVectorType', 'PropertyId',
    # data.db
    'Instance', 'Property', 'PropertyGroup', 'Tag', 'Folder', 'File', 'FileSource',
    'Sha1Value', 'InstanceValue', 'FileValue',
    'Commit', 'DataCommit', 'UpsertCommit', 'DeleteCommit',
    # media.db
    'Image', 'ImageType', 'Vector', 'VectorType', 'Map',
]
