import importlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from panoptic.core.plugin import clone_repo
from panoptic.core.project import verify_panoptic_data
from panoptic.core.project.project import Project
from panoptic.models import PluginKey, PanopticData, ProjectId, PluginType
from panoptic.utils import get_datadir, convert_old_panoptic_json


class Panoptic:
    def __init__(self):
        self.global_file_path = get_datadir() / 'panoptic' / 'projects.json'
        verify_panoptic_data()
        self.data = self.load_data()
        self.project_id = None
        self.project: Project | None = None

    def load_data(self):
        try:
            with open(self.global_file_path, 'r') as file:
                data = json.load(file)
                data, save = convert_old_panoptic_json(data)
                loaded_data = PanopticData(**data)
        except (FileNotFoundError, json.JSONDecodeError):
            loaded_data = PanopticData(projects=[])

        if save:
            self.data = loaded_data
            self.save_data()
        return loaded_data

    def save_data(self):
        directory = os.path.dirname(self.global_file_path)
        # Create the directory if it doesn't exist
        if not os.path.exists(directory):
            os.makedirs(directory)
        with open(self.global_file_path, 'w') as file:
            json.dump(self.data.model_dump(), file, indent=2)

    async def create_project(self, name, path):
        if any(project.path == path for project in self.data.projects):
            raise f"A project_id with path '{path}' already exists."
        # else:
        if not os.path.exists(path):
            os.makedirs(path)
        project = ProjectId(name=name, path=path)
        self.data.projects.append(project)
        await self.load_project(path)

    async def import_project(self, path: str):
        p = Path(path)
        if not (p / 'panoptic.db').exists():
            raise ValueError('Folder is not a panoptic project_id (No panoptic.db file found)')
        if any(project.path == path for project in self.data.projects):
            raise f"ProjectId is already imported."
        project = ProjectId(path=str(p), name=str(p.name))
        self.data.projects.append(project)
        # await self.load_project(path)

    def remove_project(self, path):
        self.data.projects = [p for p in self.data.projects if p.path != path]
        self.save_data()

    def rename_project(self, path, new_name):
        for project in self.data.projects:
            if project.path == path:
                project.name = new_name
        if self.data.last_opened and self.data.last_opened.path == path:
            self.data.last_opened.name = new_name
        self.save_data()

    async def load_project(self, path):
        try:
            for project in self.data.projects:
                if str(project.path) == str(path):
                    self.save_data()
                    self.project_id = project

                    if self.project:
                        await self.project.close()
                    plugins = self.data.plugins
                    if path in self.data.ignored_plugins:
                        plugins = [p for p in plugins if p.name not in self.data.ignored_plugins[path]]
                    self.project = Project(path, plugins)
                    await self.project.start()

                    from panoptic.routes.project_routes import set_project
                    set_project(self.project)
                    return True
        except Exception as e:
            print('Failed to load project')
            await self.close_project()
            raise e

    def add_plugin_from_path(self, path: str, name: str, source: str, plugin_type: PluginType):
        path = Path(path)
        if any(path == p.path for p in self.data.plugins):
            return
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", os.path.join(path, 'requirements.txt')])

        init_path = Path(path) / '__init__.py'
        if not init_path.exists():
            raise Exception(f'No __init__.py file found at {path}')
        self.data.plugins.append(PluginKey(name=name, path=str(path), source=source, type=plugin_type))
        self.save_data()

    def add_plugin_from_pip(self, source: str, name: str = None):
        name = name or source
        self.update_plugin_from_pip(source)
        self.data.plugins.append(PluginKey(name=name, source=source, type=PluginType.pip))
        self.save_data()
        # module = importlib.import_module(source)
        # return module.__path__

    def update_plugin(self, name: str):
        plugin = [p for p in self.data.plugins if p.name == name][0]
        if plugin.type == PluginType.pip:
            self.update_plugin_from_pip(plugin.source)
            return True
        path = plugin.path
        if plugin.type == PluginType.git:
            path = clone_repo(plugin.source, plugin.name)
        self.update_plugin_from_path(path)
        return True

    def update_plugin_from_path(self, path: str):
        path = Path(path)
        # check that the plugin is registered
        if not any(str(path) == p.path for p in self.data.plugins):
            return
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", os.path.join(path, 'requirements.txt')])

    def update_plugin_from_pip(self, source: str):
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-U", source])

    def del_plugin_path(self, name: str):
        removed = next(p for p in self.data.plugins if p.name == name)
        for project in self.data.projects:
            plugin_data_path = Path(project.path) / "plugin_data" / removed.name.lower()
            try:
                shutil.rmtree(plugin_data_path)
            except Exception as e:
                print(e)
        if removed.source:
            try:
                shutil.rmtree(removed.path)
            except Exception as e:
                print(e)
        self.data.plugins = [p for p in self.data.plugins if p.name != name]
        self.save_data()

    def get_plugin_paths(self):
        return self.data.plugins

    async def close_project(self):
        self.project_id = None
        self.data.last_opened = None
        self.save_data()
        if self.project:
            await self.project.close()
        self.project = None
        from panoptic.routes.project_routes import set_project
        set_project(self.project)

    async def set_ignored_plugin(self, project: str, plugin: str, value: bool):
        if project not in self.data.ignored_plugins:
            self.data.ignored_plugins[project] = []
        if value and plugin not in self.data.ignored_plugins[project]:
            self.data.ignored_plugins[project].append(plugin)
        if not value:
            self.data.ignored_plugins[project] = [p for p in self.data.ignored_plugins[project] if p != plugin]
        self.save_data()
        return self.data.ignored_plugins

    async def close(self):
        await self.close_project()

    def is_loaded(self):
        return self.project_id is not None
