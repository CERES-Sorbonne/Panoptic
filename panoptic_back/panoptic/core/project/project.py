import atexit
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List, Any

from showinfm import show_in_file_manager

from panoptic.core.db.db_connection import DbConnection
from panoptic.core.exporter import Exporter
from panoptic.core.importer import Importer
from panoptic.core.project.project_actions import ProjectActions
from panoptic.core.project.project_db import ProjectDb
from panoptic.core.project.project_events import ProjectEvents
from panoptic.core.project.project_ui import ProjectUi
from panoptic.core.project.undo_queue import UndoQueue
from panoptic.core.task.import_image_task import ImportInstanceTask
from panoptic.core.task.load_plugin_task import LoadPluginTask
from panoptic.core.task.task_queue import TaskQueue
from panoptic.models import StatusUpdate
from panoptic.core.plugin.plugin import Plugin

nb_workers = 4


def get_executor():
    executor = ThreadPoolExecutor(max_workers=nb_workers)
    atexit.register(executor.shutdown)
    return executor


class Project:
    def __init__(self, folder_path: str, plugins: List[str]):
        self.executor = get_executor()
        self.is_loaded = False
        self.base_path = folder_path
        self.db: ProjectDb | None = None
        self.ui: ProjectUi | None = None
        self.on = ProjectEvents()
        self.action = ProjectActions()
        self.task_queue = TaskQueue(self.executor, num_workers=4)
        self.importer = Importer(project=self)
        self.exporter = Exporter(project=self)
        self.undo_queue: UndoQueue | None = None

        self.plugin_loaded = False
        self.plugins: List[Plugin] = []
        self.plugin_paths = plugins

    async def start(self):
        conn = DbConnection(self.base_path)
        await conn.start()
        self.db = ProjectDb(conn)
        self.ui = ProjectUi(self.db.get_raw_db())

        self.db.on_import_instance.redirect(self.on.import_instance)
        # from panoptic.plugins import DefaultPlugin
        # paths = [DefaultPlugin.__file__, *self.plugin_paths]
        paths = self.plugin_paths
        for plugin_path in paths:
            task = LoadPluginTask(self, plugin_path)
            self.task_queue.add_task(task)

        self.undo_queue = UndoQueue(self.db)

        self.is_loaded = True

    async def redirect_on_import(self, x):
        self.on.import_instance.emit(x)

    def get_status_update(self) -> StatusUpdate:
        res = StatusUpdate(update=self.ui.update_counter)
        res.tasks = self.task_queue.get_task_states()
        res.plugin_loaded = self.plugin_loaded
        return res

    async def close(self):
        self.is_loaded = False
        self.base_path = ''
        await self.db.close()

    async def export_data(self, name: str = None, ids: [int] = None, properties: [int] = None,
                          copy_images: bool = False):
        export_path = await self.exporter.export_data(name=name, path=self.base_path, instance_ids=ids,
                                                      properties=properties,
                                                      copy_images=copy_images)
        # export_path = "lala"
        show_in_file_manager(export_path)
        return export_path

    async def plugins_info(self):
        return [await p.get_description() for p in self.plugins]

    async def import_folder(self, folder: str):
        folder = os.path.normpath(folder)
        all_files = [os.path.join(path, name) for path, subdirs, files in os.walk(folder) for name in files]
        all_images = [i for i in all_files if
                      i.lower().endswith('.png') or i.lower().endswith('.jpg') or i.lower().endswith('.jpeg')]

        folder_node, file_to_folder_id = await self._compute_folder_structure(folder, all_images)

        tasks = [ImportInstanceTask(project=self, file=file, folder_id=file_to_folder_id[file])
                 for file in all_images]
        [self.task_queue.add_task(t) for t in tasks]

    async def _compute_folder_structure(self, root_path, all_files: List[str]):
        offset = len(root_path)
        root, root_name = os.path.split(root_path)
        root_folder = await self.db.add_folder(root_path, root_name)
        file_to_folder_id = {}
        for file in all_files:
            path, name = os.path.split(file)
            if offset == len(path):
                file_to_folder_id[file] = root_folder.id
                continue
            path = path[offset + 1:]
            parts = Path(path).parts
            current_folder = root_folder
            for part in parts:
                if part not in current_folder.children:
                    child = await self.db.add_folder(current_folder.path + '/' + part, part, current_folder.id)
                    current_folder.children[part] = child
                else:
                    child = current_folder.children[part]
                file_to_folder_id[file] = child.id
                current_folder = child
        return root_folder, file_to_folder_id

    async def set_plugin_params(self, plugin_name: str, params: Any):
        plugin = [p for p in self.plugins if p.name == plugin_name]
        if not plugin:
            return
        plugin = plugin[0]
        await plugin.update_params(params)
        return plugin

