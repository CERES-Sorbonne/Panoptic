import json
import os
from pathlib import Path

from pydantic import BaseModel

from panoptic.utils import get_datadir


class Project(BaseModel):
    name: str | None
    path: str | None


class PanopticData(BaseModel):
    projects: list[Project]
    last_opened: Project | None = None


class Panoptic:
    def __init__(self):
        self.global_file_path = get_datadir() / 'panoptic' / 'projects.json'
        self.data = self.load_data()
        self.project = None

    def load_data(self):
        try:
            with open(self.global_file_path, 'r') as file:
                data = json.load(file)
                return PanopticData(**data)
        except (FileNotFoundError, json.JSONDecodeError):
            return PanopticData(projects=[])

    def save_data(self):
        with open(self.global_file_path, 'w') as file:
            json.dump(self.data.dict(), file, indent=2)

    def create_project(self, name, path):
        if any(project.path == path for project in self.data.projects):
            raise f"A project with path '{path}' already exists."
        # else:
        if not os.path.exists(path):
            os.makedirs(path)
        project = Project(name=name, path=path)
        self.data.projects.append(project)
        self.load_project(path)

    def import_project(self, path: str):
        p = Path(path)
        if not (p / 'panoptic.db').exists():
            raise ValueError('Folder is not a panoptic project (No panoptic.db file found)')
        if any(project.path == path for project in self.data.projects):
            raise f"Project is already imported."
        project = Project(path=str(p), name=str(p.name))
        self.data.projects.append(project)
        self.load_project(path)

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

    def load_project(self, path):
        for project in self.data.projects:
            if str(project.path) == str(path):
                self.save_data()
                self.project = project

    def close(self):
        self.project = None
        self.data.last_opened = {}
        self.save_data()

    def is_loaded(self):
        return self.project is not None


panoptic = Panoptic()
