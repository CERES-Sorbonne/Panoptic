import asyncio
import logging
import traceback
from pathlib import Path

from PIL.Image import Image
from pydantic import BaseModel
import panoptic

from panoptic_api.core import db


class ProcessTask(BaseModel):
    sha1: str
    image: Image

    class Config:
        arbitrary_types_allowed = True


SENTINEL = 'STOP'


class TransformManager:
    def __init__(self, root: str):
        # where result will be stored
        self._root = Path(root)
        self._total = 0
        self._task = None
        # process images here
        self._queue = asyncio.Queue()
        # if at some point we multiprocess the transform of the images, might need another queue to put result in db
        # since sqlite not concurrent

    @property
    def is_running(self):
        return self._task and not self._task.done()

    def processed(self):
        return (self._total - self._queue.qsize()) / self._total * 100

    async def process_queue(self):
        """
        Process Queue Loop
        Works through the queue one by one.
        @return:
        """
        self._root.mkdir(parents=True, exist_ok=True)
        while True:
            try:
                # if nothing to do, end process
                if self._queue.qsize() == 0:
                    return
                task: ProcessTask = await self._queue.get()
                # Stop if Sentinel is detected
                if task == SENTINEL:
                    return
                await self.transform_image_task(task)
            except Exception as e:
                logging.error(traceback.print_exc(limit=3))
                logging.error('Error inside _process_queue function : ' + e.__str__())

    def start(self):
        self._task = asyncio.create_task(self.process_queue())

    @staticmethod
    async def transform_image_task(task: ProcessTask):
        # TODO: maybe move this function in core ? later if it works
        # TODO: use multiprocessing here ?
        ahash = panoptic.to_average_hash(task.image)
        # TODO: find a way to access all the images for PCA
        vector = panoptic.to_vector(task.image)
        # TODO: maybe add another queue to avoid bottleneck on db
        db.update_image_hashs(task.sha1, ahash, vector)

    def process_image(self, sha1: str, image: Image):
        self._queue.put_nowait(ProcessTask(sha1=sha1, image=image))
        if not self.is_running:
            self.start()