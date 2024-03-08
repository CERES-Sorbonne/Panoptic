import json
import os
from asyncio import sleep
from pathlib import Path
from typing import List

from pydantic import BaseModel

from panoptic.core.project.project import Project
from panoptic.utils import get_datadir


class ProjectId(BaseModel):
    name: str | None = None
    path: str | None = None


class PanopticData(BaseModel):
    projects: list[ProjectId]
    last_opened: ProjectId | None = None
    plugins: List[str] = []


class Panoptic:
    def __init__(self):
        self.global_file_path = get_datadir() / 'panoptic' / 'projects.json'
        self.data = self.load_data()
        self.project_id = None
        self.project: Project | None = None

        if not self.data.plugins:
            from panoptic.plugins import FaissPlugin
            module_path = os.path.abspath(FaissPlugin.__file__)
            module_path = module_path.replace('__init__.py', '')
            self.data.plugins.append(module_path)

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
        await self.load_project(path)

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
                self.project = Project(path, self.data.plugins)
                await self.project.start()

                from panoptic.routes.project_routes import set_project
                set_project(self.project)

    def add_plugin_path(self, path: str):
        if path in self.data.plugins:
            return
        init_path = Path(path) / '__init__.py'
        if not init_path.exists():
            raise Exception(f'No __init__.py file found at {path}')
        self.data.plugins.append(path)
        self.save_data()

    def del_plugin_path(self, path: str):
        if path in self.data.plugins:
            self.data.plugins.remove(path)
            self.save_data()

    def get_plugin_paths(self):
        return self.data.plugins

    async def close_project(self):
        self.project_id = None
        self.data.last_opened = {}
        self.save_data()
        await self.project.close()
        self.project = None
        from panoptic.routes.project_routes import set_project
        set_project(self.project)

    async def close(self):
        if self.project:
            await self.project.close()

    def is_loaded(self):
        return self.project_id is not None
