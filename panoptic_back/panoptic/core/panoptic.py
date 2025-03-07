import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from panoptic.core.project import verify_panoptic_data
from panoptic.core.project.project import Project
from panoptic.models import PluginKey, PanopticData, ProjectId
from panoptic.utils import get_datadir


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
                return PanopticData(**data)
        except (FileNotFoundError, json.JSONDecodeError):
            return PanopticData(projects=[])

    def save_data(self):
        directory = os.path.dirname(self.global_file_path)
        # Create the directory if it doesn't exist
        if not os.path.exists(directory):
            os.makedirs(directory)
        with open(self.global_file_path, 'w') as file:
            json.dump(self.data.dict(), file, indent=2)

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

    def add_plugin_path(self, path: str, name: str, source_url: str = None):
        path = Path(path)
        if any(path == p.path for p in self.data.plugins):
            return
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", os.path.join(path, 'requirements.txt')])

        init_path = Path(path) / '__init__.py'
        if not init_path.exists():
            raise Exception(f'No __init__.py file found at {path}')
        self.data.plugins.append(PluginKey(name=name, path=str(path), source_url=source_url))
        self.save_data()

    def update_plugin(self, path: str):
        path = Path(path)
        if any(path == p.path for p in self.data.plugins):
            return
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", os.path.join(path, 'requirements.txt')])

    def del_plugin_path(self, path: str):
        removed = next(p for p in self.data.plugins if p.path == path)
        for project in self.data.projects:
            plugin_data_path = Path(project.path) / "plugin_data" / removed.name.lower()
            try:
                shutil.rmtree(plugin_data_path)
            except Exception as e:
                print(e)
        if removed.source_url:
            try:
                shutil.rmtree(removed.path)
            except Exception as e:
                print(e)
        self.data.plugins = [p for p in self.data.plugins if p.path != path]
        self.save_data()

    def get_plugin_paths(self):
        return self.data.plugins

    async def close_project(self):
        self.project_id = None
        self.data.last_opened = None
        self.save_data()
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
        if self.project:
            await self.project.close()

    def is_loaded(self):
        return self.project_id is not None
