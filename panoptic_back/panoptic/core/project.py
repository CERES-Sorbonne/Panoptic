from panoptic.core import importer
from panoptic.db import db_utils


class Project2:
    def __init__(self, folder_path: str = None):
        self.is_loaded = False
        self.base_path = ''
        if folder_path:
            self.load(folder_path)

    async def load(self, folder_path: str):
        self.base_path = folder_path
        await db_utils.load_project(folder_path)
        importer.set_project_path(folder_path)
        self.is_loaded = True

    async def close(self):
        self.is_loaded = False
        self.base_path = ''
        await db_utils.close()
