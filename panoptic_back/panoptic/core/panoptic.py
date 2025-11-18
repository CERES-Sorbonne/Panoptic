import asyncio
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from importlib import metadata
from pathlib import Path

from panoptic.core.panoptic_db.db_connection import DbConnection
from panoptic.core.panoptic_db.panoptic_db import PanopticDb
from panoptic.core.plugin import clone_repo
from panoptic.core.project import verify_panoptic_data
from panoptic.core.project.project import Project
from panoptic.models import PluginKey, PanopticData, ProjectId, PanopticState, ProjectRef, ProjectRef2
from panoptic.utils import get_datadir
from panoptic import __version__ as panoptic_version
from panoptic.models import PluginKey, PanopticData, ProjectId, PluginType
from panoptic.utils import get_datadir, convert_old_panoptic_json


PANOPTICML_PLUGIN_PIP_NAME = 'panopticml'
PANOPTICML_PLUGIN_RESERVED_NAME = 'panopticml'

class Panoptic:
    def __init__(self, data_path: str = None):
        self.global_file_path = get_datadir() / 'panoptic' / 'projects.json'

        db_name = os.getenv("PANOPTIC_DB_NAME", "panoptic.db")
        self.sqlite_file_path = get_datadir() / 'panoptic' / db_name

        if data_path:
            self.sqlite_file_path = Path(data_path)

        verify_panoptic_data()
        self.data = PanopticData(projects=[])
        self.project_id = None
        self.project: Project | None = None
        self.open_projects: dict[int, Project] = {}
        self.version = panoptic_version

        self.db: PanopticDb | None = None

    def start(self):
        """Synchronous wrapper - runs all async operations in one event loop"""
        async def _start():
            conn = DbConnection(self.sqlite_file_path)
            await conn.start()
            self.db = PanopticDb(conn)
            self.data = await self.db.get_data()
            self.check_for_official_plugin()

        asyncio.run(_start())
        return


    def check_for_official_plugin(self):
        if os.getenv("PANOPTIC_ENV", "PROD") == "DEV":
            return
        vision_plugin = [p for p in self.data.plugins if p.source == PANOPTICML_PLUGIN_PIP_NAME and p.type == PluginType.pip]
        if vision_plugin:
            return

        # no ml plugin registered, check if it was already installed before
        ml = importlib.util.find_spec(PANOPTICML_PLUGIN_PIP_NAME)
        if ml:
            self.data.plugins.append(PluginKey(
                name=PANOPTICML_PLUGIN_RESERVED_NAME,
                type=PluginType.pip,
                path=ml.origin,
                source=PANOPTICML_PLUGIN_PIP_NAME))


    async def create_project(self, name, path):
        if any(project.path == path for project in self.data.projects):
            raise f"A Project with path '{path}' is already imported into panoptic."
        # else:
        if not os.path.exists(path):
            os.makedirs(path)

        project = ProjectRef2(name=name, path=path)
        project = await self.db.import_project(project)
        self.data = await self.db.get_data()
        return project

    async def import_project(self, path: str):
        p = Path(path)
        if not (p / 'panoptic.db').exists():
            raise ValueError(f'Folder [{p}] is not a panoptic Project (No panoptic.db file found)')
        if any(project.path == path for project in self.data.projects):
            raise f"A Project with path '{path}' is already imported into panoptic."

        project = ProjectRef2(name=p.name, path=path)
        project = await self.db.import_project(project)
        self.data = await self.db.get_data()

        return project

    async def remove_project(self, project_id: int):
        if project_id in self.open_projects:
            return
        await self.db.delete_project(project_id)
        self.data.projects = await self.db.get_projects()

    async def update_project(self, project_id: int, new_name: str, ignored_plugins: list[str]):
        project = next(p for p in self.data.projects if p.id == project_id)
        if not project:
            return
        project.name = new_name
        project.ignored_plugins = ignored_plugins
        await self.db.import_project(project)
        self.data.projects = await self.db.get_projects()

    async def load_project(self, project_id):
        project = None
        try:
            proj = next(p for p in self.data.projects if p.id == project_id)

            if project_id in self.open_projects:
                project = self.open_projects[project_id]

            if not project:
                plugins = self.data.plugins
                plugins = [p for p in plugins if p.name not in proj.ignored_plugins]

                project = Project(proj.path, plugins, proj.name, project_id)
                await project.start()
                self.open_projects[project_id] = project

            return project
        except StopIteration:
            raise ValueError(f'_project id {project_id} not found')
        except Exception as e:
            print('Failed to load _project')
            if project:
                await self.close_project(project_id)
            raise e

    async def add_plugin(self, name: str, source: str, ptype: PluginType):
        for installed_plugin in self.data.plugins:
            if installed_plugin.type == ptype and installed_plugin.source == source:
                print(f"Plugin {name} already installed", self.data.plugins)
                return
        if ptype == PluginType.pip:
            return await self.add_plugin_from_pip(source, name)
        else:
            path = source
            if ptype == PluginType.git:
                path = clone_repo(source, name)
            return await self.add_plugin_from_path(path, name, source, ptype)

    async def add_plugin_from_path(self, path: str, name: str, source: str, plugin_type: PluginType):
        path = Path(path)
        if any(path == p.path for p in self.data.plugins):
            return
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", os.path.join(path, 'requirements.txt')])

        init_path = Path(path) / '__init__.py'
        if not init_path.exists():
            raise Exception(f'No __init__.py file found at {path}')
        plugin = PluginKey(name=name, path=str(path), source=source, type=plugin_type)
        await self.db.import_plugin(plugin)
        self.data.plugins = await self.db.get_plugins()

    async def add_plugin_from_pip(self, source: str, name: str = None):
        name = name or source
        path = self.update_plugin_from_pip(source)
        plugin = PluginKey(name=name, source=source, type=PluginType.pip, path=path)
        await self.db.import_plugin(plugin)
        self.data.plugins = await self.db.get_plugins()

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
        dist = metadata.distribution(source)
        path = str(dist.locate_file("")) + '/' + source
        return path

    async def del_plugin_path(self, name: str):
        removed = next(p for p in self.data.plugins if p.name == name)
        for project in self.data.projects:
            plugin_data_path = Path(project.path) / "plugin_data" / removed.name.lower()
            try:
                shutil.rmtree(plugin_data_path)
            except Exception as e:
                print(e)
        if removed.type == PluginType.git:
            try:
                shutil.rmtree(removed.path)
            except Exception as e:
                print(e)
        await self.db.delete_plugin(removed.name)
        self.data.plugins = await self.db.get_plugins()

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

    def close(self):
        asyncio.run(self._close())

    async def _close(self):
        for project in self.open_projects.values():
            await project.close()

        await self.db.close()


    async def get_state(self):
        project_states = []
        plugins = self.data.plugins

        for p_info in self.data.projects:
            is_open = p_info.id in self.open_projects
            ignored = p_info.ignored_plugins

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
