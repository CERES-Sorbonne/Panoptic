"""Panoptic plugin SDK: write a plugin that runs in its own process and talks to the Panoptic
backend over a WebSocket (JSON-RPC 2.0), reading the project databases directly.

See technical_docs/rust_port/PLUGIN_PROTOCOL.md for the protocol and PORTING.md for the
migration from the in-process API.
"""
from .models import (
    ActionContext, ActionResult, Commit, CommitResult, DataCommit, File, FilePath, FileSource,
    FileValue, Folder, FolderPath, Group, ImageType, InputFile, Instance, InstanceValue, Map, Notif,
    NotifFunction, NotifType, OwnVectorType, Property, PropertyGroup, PropertyId, Score, ScoreList,
    Sha1Value, Tag, Vector, VectorType,
)
from .plugin import Plugin, action
from .project import ProjectData
from .protocol import OP_CREATE, OP_DELETE, OP_UPDATE, PROTOCOL_VERSION, SDK_VERSION
from .rpc import RpcError
from .tasks import FunctionTask, Task, TaskCancelled

__version__ = SDK_VERSION

__all__ = [
    'Plugin', 'action', 'ProjectData', 'Task', 'FunctionTask', 'TaskCancelled', 'RpcError',
    'ActionContext', 'ActionResult', 'Group', 'Score', 'ScoreList', 'Notif', 'NotifType', 'NotifFunction',
    'PropertyId', 'OwnVectorType', 'InputFile', 'FolderPath', 'FilePath',
    'Instance', 'File', 'Folder', 'FileSource', 'Property', 'PropertyGroup', 'Tag',
    'InstanceValue', 'Sha1Value', 'FileValue', 'DataCommit', 'Commit', 'CommitResult',
    'VectorType', 'Vector', 'Map', 'ImageType',
    'OP_CREATE', 'OP_UPDATE', 'OP_DELETE', 'PROTOCOL_VERSION', 'SDK_VERSION',
]
