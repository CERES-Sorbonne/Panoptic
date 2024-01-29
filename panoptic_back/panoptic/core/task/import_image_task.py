import hashlib
import os

from PIL import Image

from panoptic.core.project.project_db import ProjectDb
from panoptic.core.task.task import Task


class ImportInstanceTask(Task):
    def __init__(self, db: ProjectDb, file: str, folder_id: int):
        super().__init__(priority=True)
        self.db = db
        self.file = file
        self.folder_id = folder_id
        self.name = 'Import Image'


    async def run(self):
        name = self.file.split(os.sep)[-1]
        extension = name.split('.')[-1]
        folder_id = self.folder_id

        raw_db = self.db.get_raw_db()

        db_image = await raw_db.has_image_file(folder_id, name, extension)
        if db_image:
            self.db.on_import_instance.emit(db_image)
            return db_image

        sha1, url, width, height = await self._async(self._import_image, self.file, raw_db.get_project_path())

        image = await self.db.add_instance(folder_id, name, extension, sha1, url, width, height)
        # print(f'imported image: {image.id} : {image.sha1}')
        return image

    @staticmethod
    def _import_image(file_path, project_path: str):
        image = Image.open(file_path)
        width, height = image.size
        sha1_hash = hashlib.sha1(image.tobytes()).hexdigest()
        # TODO: gérer l'url statique quand on sera en mode serveur
        # url = os.path.join('/static/' + global_file_path.split(os.getenv('PANOPTIC_ROOT'))[1].replace('\\', '/'))
        if not os.path.exists(os.path.join(project_path, "mini")):
            os.mkdir(os.path.join(project_path, "mini"))
        url = f"/images/{file_path}"
        image = image.convert('RGB')
        mini = image.copy()
        mini.thumbnail(size=(200, 200))
        mini.save(os.path.join(project_path, "mini", sha1_hash + '.jpeg'), optimize=True, quality=30)

        del image
        del mini
        # gc.collect()

        return sha1_hash, url, width, height
