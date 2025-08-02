import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from panoptic.core.project import verify_panoptic_data
from panoptic.core.project.project import Project
from panoptic.models import PluginKey, PanopticData, ProjectId, PanopticState, ProjectRef
from panoptic.utils import get_datadir
from panoptic import __version__ as panoptic_version


class Panoptic:
    def __init__(self):
        self.global_file_path = get_datadir() / 'panoptic' / 'projects.json'
        verify_panoptic_data()
        self.data = self.load_data()
        self.open_projects: dict[int, Project] = {}
        self.version = panoptic_version

    def load_data(self):
        try:
            if not os.path.exists(self.global_file_path):
                raise FileNotFoundError

            with open(self.global_file_path, 'r') as file:
                data = json.load(file)
                res = PanopticData(**data)
                for i in range(len(res.projects)):
                    res.projects[i].id = i+1
                return res
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Warning: Could not load projects.json. Error: {e}", file=sys.stderr)
            if isinstance(e, json.JSONDecodeError):
                # If the file is corrupted, back it up before starting fresh
                corrupt_file_path = self.global_file_path
                if os.path.exists(corrupt_file_path):
                    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                    backup_path = f"{corrupt_file_path}.corrupt.{timestamp}.bak"
                    shutil.copy(corrupt_file_path, backup_path)
                    print(f"A backup of the corrupt file has been saved to: {backup_path}", file=sys.stderr)

            print("Starting with a new empty project list.", file=sys.stderr)
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

        max_id = 0
        if len(self.data.projects):
            max_id = max([p.id for p in self.data.projects])
        project = ProjectId(name=name, path=path, id=max_id + 1)
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
        project = None
        self.save_data()
        try:
            proj = next(p for p in self.data.projects if str(p.path) == str(path))
            project_id = proj.id
            if project_id is None:
                raise ValueError(f'project path {path} not found')
            if project_id in self.open_projects:
                project = self.open_projects[project_id]
            if not project:
                plugins = self.data.plugins
                if path in self.data.ignored_plugins:
                    plugins = [p for p in plugins if p.name not in self.data.ignored_plugins[path]]

                project = Project(path, plugins, proj.name, project_id)
                await project.start()
                self.open_projects[project.id] = project

            return project
        except Exception as e:
            print('Failed to load project')
            if project:
                await self.close_project(project.id)
            raise e

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

    def get_project(self, project_id: int):
        if project_id in self.open_projects:
            return self.open_projects[project_id]
        return None

    async def close_project(self, project_id: int):
        project = self.get_project(project_id)
        if not project:
            return

        await project.close()
        del self.open_projects[project_id]

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
        for project in self.open_projects.values():
            await project.close()

    async def get_state(self):
        project_states = []
        plugins = self.data.plugins

        for p_info in self.data.projects:
            is_open = p_info.id in self.open_projects
            ignored = self.data.ignored_plugins.get(p_info.path, [])

            state = ProjectRef(
                id=p_info.id,
                name=p_info.name,
                path=p_info.path,
                is_open=is_open,
                ignored_plugins=ignored
            )
            project_states.append(state)

        return PanopticState(
            version=self.version,
            projects=project_states,
            plugins=list(plugins)
        )
