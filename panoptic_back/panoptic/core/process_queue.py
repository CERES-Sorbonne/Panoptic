import asyncio
import gc
import hashlib
import logging
import os
import sys
import traceback
from concurrent.futures import Executor
from typing import List, Callable, Dict

from PIL import Image

import panoptic.compute as compute
from panoptic.core import db
from panoptic.models import ImageImportTask

logger = logging.getLogger('ProcessQueue')


class ProcessQueue:
    def __init__(self, executor: Executor):
        self.executor = executor

        self._queue = asyncio.Queue()
        self._workers: List[asyncio.Task] = []
        self._working: Dict[int, bool] = {}
        self.done_callback = None

    def start_workers(self, workers=1):
        if self._workers:
            return
        for i in range(workers):
            self._workers.append(asyncio.create_task(self._process_queue(i)))

    def add_task(self, task):
        self._queue.put_nowait(task)

    def done(self):
        return self._queue.qsize() == 0

    async def _process_queue(self, worker_id: int):
        while True:
            try:
                # if nothing left to do remove working flag
                if self.done():
                    self._working[worker_id] = False

                task = await self._queue.get()
                # set working flag
                self._working[worker_id] = True

                res = await self._process_task(task)
                if self.done_callback:

                    is_last = self.done() and self.get_working_nb() == 1
                    self.done_callback(res, is_last)
            except Exception as e:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                logger.error("".join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
                logger.error(e)

    def get_working_nb(self):
        working = [v for v in self._working.values() if v]
        return len(working)

    async def _process_task(self, task):
        raise NotImplementedError()

    async def _execute_in_process(self, fnc: Callable, *args):
        return await asyncio.wrap_future(self.executor.submit(fnc, *args))


class ImportImageQueue(ProcessQueue):
    def add_task(self, task: ImageImportTask):
        super().add_task(task)

    async def _process_task(self, task: ImageImportTask):
        # print('process: ', task.image_path, task.folder_id)
        name = task.image_path.split(os.sep)[-1]
        extension = name.split('.')[-1]
        folder_id = task.folder_id

        db_image = await db.has_image_file(folder_id, name, extension)
        if db_image:
            return db_image

        sha1, url, width, height = await self._execute_in_process(self._import_image, task.image_path)

        image = await db.add_image(folder_id, name, extension, sha1, url, width, height)
        # print(f'imported image: {image.id} : {image.sha1}')
        return image

    @staticmethod
    def _import_image(file_path):
        image = Image.open(file_path)
        width, height = image.size
        sha1_hash = hashlib.sha1(image.tobytes()).hexdigest()
        # TODO: gérer l'url statique quand on sera en mode serveur
        # url = os.path.join('/static/' + file_path.split(os.getenv('PANOPTIC_ROOT'))[1].replace('\\', '/'))
        url = f"/images/{file_path}"
        image = image.convert('RGB')
        mini = image.copy()
        mini.thumbnail(size=(200, 200))
        mini.save(os.path.join(os.environ['PANOPTIC_DATA'], "mini", sha1_hash + '.jpeg'), optimize=True, quality=30)

        del image
        del mini
        # gc.collect()

        return sha1_hash, url, width, height


class ComputeVectorsQueue(ProcessQueue):
    async def _process_task(self, task):
        image_id: int = task
        image = (await db.get_images(ids=[image_id]))[0]
        computed = await db.get_sha1_computed_values([image.sha1])
        if computed:
            return computed

        folder = await db.get_folder(image.folder_id)
        file_path = f"{folder.path}/{image.name}"
        ahash, vector = await self._execute_in_process(self.compute_image, file_path)
        res = await db.set_computed_value(sha1=image.sha1, ahash=ahash, vector=vector)
        del vector
        # gc.collect()
        print('computed image: ', image_id, '  :  ', res.sha1)
        return res

    @staticmethod
    def compute_image(image_path: str):
        image = Image.open(image_path)
        image = image.convert('RGB')
        ahash = str(compute.to_average_hash(image))
        # TODO: find a way to access all the images for PCA
        vector = compute.to_vector(image)

        del image
        # gc.collect()

        return ahash, vector
