import io
import logging

import aiofiles
from PIL import Image

from panoptic.core.plugin.plugin_project_interface import PluginProjectInterface
from panoptic.core.task.task import Task
from panoptic.models import Instance, Vector
from . import compute
from .create_faiss_index import compute_faiss_index

logger = logging.getLogger('FaissPlugin:VectorTask')


class ComputeVectorTask(Task):
    def __init__(self, project: PluginProjectInterface, source: str, type_: str, instance: Instance):
        super().__init__()
        self.project = project
        self.source = source
        self.type = type_
        self.instance = instance
        self.name = 'Clip Vectors'

    async def run(self):
        # instance_id = self.instance.id
        instance = self.instance
        exist = await self.project.vector_exist(self.source, self.type, instance.sha1)
        if exist:
            return

        image_data = await self.project.get_project().db.get_large_image(instance.sha1)
        if not image_data:
            file = instance.url
            async with aiofiles.open(file, mode='rb') as file:
                image_data = await file.read()

        vector_data = await self._async(self.compute_image, image_data, self.project.base_path)
        vector = Vector(self.source, self.type, instance.sha1, vector_data)
        res = await self.project.add_vector(vector)
        del vector
        # gc.collect()
        # logging.info('computed image: ', instance.id, '  :  ', res.sha1)
        return res

    async def run_if_last(self):
        await compute_faiss_index(self.project.base_path, self.project, self.source, self.type)
        logging.info('computed faiss index')

    @staticmethod
    def compute_image(image_data: bytes, project_path: str):
        image = Image.open(io.BytesIO(image_data))
        image = image.convert('RGB')
        vector = compute.to_vector(image, project_path)

        del image
        # gc.collect()

        return vector
