# from panoptic.core.exporter import export_data
from panoptic.core.exporter import export_data
from showinfm import show_in_file_manager


class Project:
    def __init__(self, folder_path: str = None):
        self.is_loaded = False
        self.base_path = ''
        if folder_path:
            self.load(folder_path)

    async def load(self, folder_path: str):
        self.base_path = folder_path
        self.is_loaded = True

    async def close(self):
        self.is_loaded = False
        self.base_path = ''

    async def export_data(self, name: str = None, ids: [int] = None, properties: [int] = None, copy_images: bool = False):
        export_path = await export_data(name=name, path=self.base_path, image_ids=ids, properties=properties, copy_images=copy_images)
        # export_path = "lala"
        show_in_file_manager(export_path)
        return export_path
