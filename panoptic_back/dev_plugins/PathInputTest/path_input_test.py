# No `from __future__ import annotations` here: the action registry reads the real annotation classes.
import os

from pydantic import BaseModel

from panoptic.core.plugin.plugin import APlugin
from panoptic.models.action_models import (
    ActionContext, ActionResult, FilePath, FolderPath, InputFile, Notif, NotifType,
)


class Params(BaseModel):
    """Base settings to try the path inputs in the plugin settings panel.
    @default_folder: a folder on the server
    @default_file: a file on the server
    """
    default_folder: FolderPath = ''
    default_file: FilePath = ''


class PathInputTest(APlugin):
    """Dummy plugin to try the FolderPath, FilePath and InputFile inputs."""

    def __init__(self, name: str, project, plugin_path: str):
        self.params = Params()
        super().__init__(name=name, project=project, plugin_path=plugin_path)
        self.add_action_easy(self.show_paths, ['execute'])

    # Defaults are needed: an input left empty in the UI is not passed to the function.
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
