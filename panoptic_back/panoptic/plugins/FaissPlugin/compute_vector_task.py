import logging

from PIL import Image

from panoptic.core.project.project import Project
from panoptic.core.task.task import Task
from panoptic.models import Instance, Vector

from . import compute
from .create_faiss_index import compute_faiss_index

logger = logging.getLogger('FaissPlugin:VectorTask')


class ComputeVectorTask(Task):
    def __init__(self, project: Project, source: str, type_: str, instance: Instance):
        super().__init__()
        self.project = project
        self.source = source
        self.type = type_
        self.instance = instance
        self.name = 'Clip Vectors'

    async def run(self):
        instance_id = self.instance.id
        instance = (await self.project.db.get_instances(ids=[instance_id]))[0]
        exist = await self.project.db.vector_exist(self.source, self.type, instance.sha1)
        if exist:
            return

        folder = await self.project.db.get_folder(instance.folder_id)
        file_path = f"{folder.path}/{instance.name}"
        vector_data = await self._async(self.compute_image, file_path, self.project.base_path)
        vector = Vector(self.source, self.type, instance.sha1, vector_data)
        res = await self.project.db.add_vector(vector)
        del vector
        # gc.collect()
        logging.info('computed image: ', instance_id, '  :  ', res.sha1)
        return res

    async def run_if_last(self):
        await compute_faiss_index(self.project.base_path, self.project.db, self.source, self.type)
        logging.info('computed faiss index')

    @staticmethod
    def compute_image(image_path: str, project_path: str):
        image = Image.open(image_path)
        image = image.convert('RGB')
        vector = compute.to_vector(image, project_path)

        del image
        # gc.collect()

        return vector
