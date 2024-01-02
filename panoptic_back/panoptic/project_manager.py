import json
import os

from pydantic import BaseModel

from panoptic.utils import get_datadir


class Project(BaseModel):
    name: str | None
    path: str | None


class PanopticData(BaseModel):
    projects: list[Project]
    last_opened: Project | None = None


class ProjectManager:
    def __init__(self):
        self.file_path = get_datadir() / 'panoptic' / 'projects.json'
        self.panoptic_data = self.load_data()

    def load_data(self):
        try:
            with open(self.file_path, 'r') as file:
                data = json.load(file)
                return PanopticData(**data)
        except (FileNotFoundError, json.JSONDecodeError):
            return PanopticData(projects=[])

    def save_data(self):
        with open(self.file_path, 'w') as file:
            json.dump(self.panoptic_data.dict(), file, indent=2)

    def add_project(self, name, path):
        if any(project.path == path for project in self.panoptic_data.projects):
            raise f"A project with path '{path}' already exists."
        else:
            if not os.path.exists(os.path.join(path)):
                os.makedirs(path)
            project = Project(name=name, path=path)
            self.panoptic_data.projects.append(project)
            self.set_loaded(path)

    def remove_project(self, path):
        self.panoptic_data.projects = [p for p in self.panoptic_data.projects if p.path != path]
        if self.panoptic_data.last_opened.path == path:
            self.panoptic_data.last_opened = None
        self.save_data()

    def rename_project(self, path, new_name):
        for project in self.panoptic_data.projects:
            if project.path == path:
                project.name = new_name
        if self.panoptic_data.last_opened and self.panoptic_data.last_opened.path == path:
            self.panoptic_data.last_opened.name = new_name
        self.save_data()

    def set_loaded(self, path):
        for project in self.panoptic_data.projects:
            print(path, project.path)
            if str(project.path) == str(path):
                print(project)
                self.panoptic_data.last_opened = project
                self.save_data()
        print(self.panoptic_data.last_opened)

    def close(self):
        self.panoptic_data.last_opened = {}
        self.save_data()
