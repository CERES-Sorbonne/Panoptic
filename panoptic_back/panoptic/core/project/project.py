import asyncio
import atexit
import os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List, Any

from showinfm import show_in_file_manager

from panoptic.core.db.db_connection import DbConnection
from panoptic.core.exporter import Exporter
from panoptic.core.importer.importer import Importer
from panoptic.core.plugin.plugin import APlugin
from panoptic.core.project.plugin_watcher import PluginWatcher
from panoptic.core.project.project_actions import ProjectActions
from panoptic.core.project.project_db import ProjectDb
from panoptic.core.project.project_events import ProjectEvents
from panoptic.core.project.project_ui import ProjectUi
from panoptic.core.task.import_image_task import ImportImageTask
from panoptic.core.task.import_instance_task import ImportInstanceTask
from panoptic.core.task.load_plugin_task import LoadPluginTask
from panoptic.core.task.task_queue import TaskQueue
from panoptic.models import ProjectSettings, PluginKey, DbCommit, ProjectState, TaskState

nb_workers = 8
folder_import_seq = 1

def get_executor():
    executor = ThreadPoolExecutor(max_workers=nb_workers)
    atexit.register(executor.shutdown)
    return executor


class Project:
    def __init__(self, folder_path: str, plugins: List[PluginKey], name: str, id_: int = 0):
        self.id = id_
        self.name = name
        self._load_task = None
        self.executor = get_executor()
        self.is_loaded = False
        self.base_path = folder_path
        self.db: ProjectDb | None = None
        self.ui: ProjectUi | None = None
        self.on = ProjectEvents(self.id)
        self.action = ProjectActions()
        self.task_queue = TaskQueue(self, num_workers=nb_workers * 2)
        self.plugin_watcher = PluginWatcher(self)
        self.importer = Importer(project=self)
        self.exporter = Exporter(project=self)
        self.sha1_to_files: dict[str, list[str]] = defaultdict(list)

        self.settings = ProjectSettings()

        self.plugin_loaded = False
        self.plugins: List[APlugin] = []
        self.plugin_keys = plugins

        self.task_queue.on_update.register(self._emit_tasks)

    async def _emit_tasks(self, tasks: list[TaskState]):
        self.on.sync.emitTasks(tasks)

    async def start(self):
        conn = DbConnection(self.base_path)
        await conn.start()
        self.db = ProjectDb(conn, self)
        self.ui = ProjectUi(self.db)

        self.db.on_import_instance.redirect(self.on.import_instance)

        # avoid blocking response for UI on longer loads
        self._load_task = asyncio.create_task(self._parallel_load())


        for key in self.plugin_keys:
            should_watch = self.plugin_watcher.watching
            task = LoadPluginTask(key, should_watch)
            if should_watch:
                task.run_if_last = self.plugin_watcher.start
            self.task_queue.add_task(task)

        # await self.plugin_watcher.start()
        self.is_loaded = True

    async def wait_full_start(self):
        await self._load_task

    async def _parallel_load(self):
        await self._load_settings()
        await self._load_sha1_to_files()

    async def redirect_on_import(self, x):
        self.on.import_instance.emit(x)

    async def close(self):
        self.is_loaded = False
        self.base_path = ''
        try:
            await self.db.close()
            await self.task_queue.close()
            await self.plugin_watcher.stop()
        except Exception:
            pass

    async def export_data(self, name: str = None, ids: [int] = None, properties: [int] = None,
                          copy_images: bool = False, key: str = 'id'):
        export_path = await self.exporter.export_data(name=name, path=self.base_path, instance_ids=ids,
                                                      properties=properties,
                                                      copy_images=copy_images, key=key)
        show_in_file_manager(export_path)
        return export_path

    async def plugins_info(self):
        return [p.get_description() for p in self.plugins]

    async def import_folder(self, folder: str):
        global folder_import_seq
        folder = os.path.normpath(folder)
        all_files = [os.path.join(path, name) for path, subdirs, files in os.walk(folder) for name in files]
        all_images = [i for i in all_files if
                      i.lower().endswith('.png') or i.lower().endswith('.jpg') or i.lower().endswith(
                          '.jpeg') or i.lower().endswith('.gif') or i.lower().endswith('.webp')]

        folder_node, file_to_folder_id = await self._compute_folder_structure(folder, all_images)
        seq = folder_import_seq
        folder_import_seq +=1
        tasks = [ImportInstanceTask(seq=seq, file=file, folder_id=file_to_folder_id[file])
                 for file in all_images]
        [self.task_queue.add_task(t) for t in tasks]
        self.on.sync.emitFolders(await self.db.get_folders())

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
        self.settings = await self.db.get_project_settings()

    async def _load_sha1_to_files(self):
        async for row in self.db.stream_instance_sha1_and_url():
            self.sha1_to_files[row[0]].append(row[1])

    async def update_settings(self, settings: ProjectSettings):
        re_import_images = False

        delete_small = False
        delete_medium = False
        delete_large = False
        delete_raw = False

        # Small
        if settings.image_small_size != self.settings.image_small_size:
            delete_small = True
            if settings.save_image_small:
                re_import_images = True

        if settings.save_image_small != self.settings.save_image_small:
            if settings.save_image_small:
                re_import_images = True
            else:
                delete_small = True

        # Medium
        if settings.image_medium_size != self.settings.image_medium_size:
            delete_medium = True
            if settings.save_image_medium:
                re_import_images = True

        if settings.save_image_medium != self.settings.save_image_medium:
            if settings.save_image_medium:
                re_import_images = True
            else:
                delete_medium = True

        # Large
        if settings.image_large_size != self.settings.image_large_size:
            delete_large = True
            if settings.save_image_large:
                re_import_images = True

        if settings.save_image_large != self.settings.save_image_large:
            if settings.save_image_large:
                re_import_images = True
            else:
                delete_large = True

        # Raw
        if settings.save_file_raw != self.settings.save_file_raw:
            if settings.save_file_raw:
                re_import_images = True
            else:
                delete_raw = True

        if delete_small:
            await self.db.delete_small_images()
        if delete_medium:
            await self.db.delete_medium_images()
        if delete_large:
            await self.db.delete_large_images()
        if delete_raw:
            await self.db.delete_raw_images()

        await self.db.set_project_settings(settings)
        self.settings = settings

        if re_import_images:
            sha1s = list(self.sha1_to_files.keys())
            [self.task_queue.add_task(ImportImageTask(sha1)) for sha1 in sha1s]

    async def delete_empty_instance_clones(self):
        ids = await self.db.delete_empty_instance_clones()
        commit = DbCommit()
        commit.empty_instances = ids
        return commit

    async def delete_vector_type(self, id_: int):
        res = await self.db.delete_vector_type(id_)
        for p in self.plugins:
            await p.load_vector_types()
        return res

    def get_state(self):
        tasks = self.task_queue.get_task_states()
        plugins = [p.get_description() for p in self.plugins]
        return ProjectState(
            id=self.id,
            name=self.name,
            path=self.base_path,
            tasks=tasks,
            plugins=plugins,
            settings=self.settings)

    def add_plugin(self, plugin: APlugin):
        self.plugins.append(plugin)
        # self.on.sync.emitProjectState(self.get_state())

    async def run_async(self, function, *args):
        """
        Make function awaitable and execute in Executor
        """
        return await asyncio.wrap_future(self.executor.submit(function, *args))
