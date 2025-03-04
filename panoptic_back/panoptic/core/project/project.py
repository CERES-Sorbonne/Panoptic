import asyncio
import atexit
import os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from time import time
from pathlib import Path
from typing import List, Any

from showinfm import show_in_file_manager

from panoptic.core.db.db_connection import DbConnection
from panoptic.core.exporter import Exporter
from panoptic.core.importer.importer import Importer
from panoptic.core.plugin.plugin import APlugin
from panoptic.core.project.project_actions import ProjectActions
from panoptic.core.project.project_db import ProjectDb
from panoptic.core.project.project_events import ProjectEvents
from panoptic.core.project.project_ui import ProjectUi
from panoptic.core.task.import_image_task import ImportImageTask
from panoptic.core.task.import_instance_task import ImportInstanceTask
from panoptic.core.task.load_plugin_task import LoadPluginTask
from panoptic.core.task.task_queue import TaskQueue
from panoptic.models import StatusUpdate, ProjectSettings, PluginKey
from panoptic.utils import get_model_params_description

nb_workers = 8


def get_executor():
    executor = ThreadPoolExecutor(max_workers=nb_workers)
    atexit.register(executor.shutdown)
    return executor


class Project:
    def __init__(self, folder_path: str, plugins: List[PluginKey]):
        self._load_task = None
        self.executor = get_executor()
        self.is_loaded = False
        self.base_path = folder_path
        self.db: ProjectDb | None = None
        self.ui: ProjectUi | None = None
        self.on = ProjectEvents()
        self.action = ProjectActions()
        self.task_queue = TaskQueue(self.executor, num_workers=nb_workers*2)
        self.importer = Importer(project=self)
        self.exporter = Exporter(project=self)
        self.sha1_to_files: dict[str, list[str]] = defaultdict(list)

        self.settings = ProjectSettings()

        self.plugin_loaded = False
        self.plugins: List[APlugin] = []
        self.plugin_keys = plugins

    async def start(self):
        try:
            conn = DbConnection(self.base_path)
            await conn.start()
            self.db = ProjectDb(conn)
            self.ui = ProjectUi(self.db.get_raw_db())

            self.db.on_import_instance.redirect(self.on.import_instance)

            # avoid blocking response for UI on longer loads
            self._load_task = asyncio.create_task(self._parallel_load())

            # from panoptic.plugins import DefaultPlugin
            # paths = [DefaultPlugin.__file__, *self.plugin_paths]
            for key in self.plugin_keys:
                task = LoadPluginTask(self, key)
                self.task_queue.add_task(task)

            self.is_loaded = True
            return True
        except Exception as e:
            print(e)
            return False

    async def wait_full_start(self):
        await self._load_task

    async def _parallel_load(self):
        await self._load_settings()
        await self._load_sha1_to_files()

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
        await self.task_queue.close()

    async def export_data(self, name: str = None, ids: [int] = None, properties: [int] = None,
                          copy_images: bool = False, key: str = 'id'):
        export_path = await self.exporter.export_data(name=name, path=self.base_path, instance_ids=ids,
                                                      properties=properties,
                                                      copy_images=copy_images, key=key)
        show_in_file_manager(export_path)
        return export_path

    async def plugins_info(self):
        return [await p.get_description() for p in self.plugins]

    async def import_folder(self, folder: str):
        folder = os.path.normpath(folder)
        all_files = [os.path.join(path, name) for path, subdirs, files in os.walk(folder) for name in files]
        all_images = [i for i in all_files if
                      i.lower().endswith('.png') or i.lower().endswith('.jpg') or i.lower().endswith('.jpeg') or i.lower().endswith('.gif')]

        folder_node, file_to_folder_id = await self._compute_folder_structure(folder, all_images)

        tasks = [ImportInstanceTask(project=self, file=file, folder_id=file_to_folder_id[file])
                 for file in all_images]
        [self.task_queue.add_task(t) for t in tasks]

    async def delete_folder(self, folder_id: int):
        res = await self.db.delete_folder(folder_id)
        self.on.delete_folder.emit(res)
        return res

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

    async def _load_settings(self):
        description = get_model_params_description(self.settings)
        db = self.db.get_raw_db()
        for setting in description:
            name = setting.name
            param_value = await db.get_project_param(name)
            if param_value is not None:
                setattr(self.settings, name, param_value)
        await self.update_settings(self.settings.copy())

    async def _load_sha1_to_files(self):
        async for row in self.db.stream_instance_sha1_and_url():
            self.sha1_to_files[row[0]].append(row[1])

    async def update_settings(self, settings: ProjectSettings):
        description = get_model_params_description(self.settings)
        db = self.db.get_raw_db()
        changed = []
        for setting in description:
            name = setting.name
            old_value = await db.get_project_param(name)
            setattr(self.settings, name, old_value)
            new_value = getattr(settings, name)
            if old_value != new_value:
                changed.append((name, old_value, new_value))
        # update database options
        for update in changed:
            name, old_value, new_value = update
            await db.set_project_param(name, new_value)

        re_import_images = False
        if settings.save_image_large != self.settings.save_image_large:
            if not settings.save_image_large:
                await db.delete_large_images()
            else:
                re_import_images = True

        if settings.save_image_medium != self.settings.save_image_medium:
            if not settings.save_image_medium:
                await db.delete_medium_images()
            else:
                re_import_images = True

        if settings.save_image_small != self.settings.save_image_small:
            if not settings.save_image_small:
                await db.delete_small_images()
            else:
                re_import_images = True

        self.settings = settings

        if re_import_images:
            sha1s = list(self.sha1_to_files.keys())
            [self.task_queue.add_task(ImportImageTask(self, sha1)) for sha1 in sha1s]




