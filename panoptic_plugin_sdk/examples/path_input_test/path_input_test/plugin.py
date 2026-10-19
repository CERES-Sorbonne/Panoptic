"""Port of panoptic_back/dev_plugins/PathInputTest to the out-of-process SDK.

Differences with the in-process version:
* no constructor arguments: the name, project and data folder come from the runtime,
* actions are declared with ``@action`` (``self.add_action(fn, hooks)`` still works),
* the module may use ``from __future__ import annotations``.
"""
from __future__ import annotations

import os

from pydantic import BaseModel

from panoptic_plugin import (
    ActionContext, ActionResult, FilePath, FolderPath, InputFile, Notif, NotifType, Plugin, action,
)


class Params(BaseModel):
    """Base settings to try the path inputs in the plugin settings panel.
    @default_folder: a folder on the server
    @default_file: a file on the server
    """
    default_folder: FolderPath = ''
    default_file: FilePath = ''


class PathInputTest(Plugin):
    """Dummy plugin to try the FolderPath, FilePath and InputFile inputs."""

    Params = Params

    # Defaults are needed: an input left empty in the UI is not passed to the function.
    @action(hooks=['execute'])
    def show_paths(self, context: ActionContext, folder: FolderPath = None, file: FilePath = None,
                   upload: InputFile = None) -> ActionResult:
        """Does nothing: reports the received inputs in a notification.
        @folder: a folder on the server, picked with the file explorer
        @file: a file on the server, picked with the file explorer
        @upload: a file uploaded from the browser
        """
        lines = [
            f'folder: {folder!r} ({type(folder).__name__}, is dir: {os.path.isdir(folder or "")})',
            f'file: {file!r} ({type(file).__name__}, is file: {os.path.isfile(file or "")})',
            f'upload: {len(upload) if upload else 0} base64 chars',
        ]
        return ActionResult(notifs=[Notif(type=NotifType.INFO, name='PathInputTest', message='\n'.join(lines))])
