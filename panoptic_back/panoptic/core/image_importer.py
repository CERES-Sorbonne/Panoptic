import asyncio
import hashlib
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import List, Callable

from PIL import Image

import panoptic.compute as compute
from panoptic.core import db
from panoptic.models import Folder


class ImageImporter:
    def __init__(self, executor: ProcessPoolExecutor):
        self.status = 'read'
        self.executor = executor
        self.import_tasks = set()
        self.compute_tasks = set()

        self.total_import = 0
        self.current_import = 0

        self.total_compute = 0
        self.current_computed = 0

        self._final_callback = None
    # def _reset_counters(self):
    #     self.total_import = -1
    #     self.current_import = 0

    async def import_folder(self, callback, folder: str):
        if self.total_import == self.current_import:
            self.total_compute = 0
            self.current_computed = 0

        all_files = [os.path.join(path, name) for path, subdirs, files in os.walk(folder) for name in files]
        all_images = [i for i in all_files if
                      i.lower().endswith('.png') or i.lower().endswith('.jpg') or i.lower().endswith('.jpeg')]
        self.total_import += len(all_images)

        folder_node, file_to_folder_id = await compute_folder_structure(folder, all_images)

        self.status = 'compute'
        tasks = [asyncio.create_task(
            self.wrap_import(
                self.executor.submit(import_image, file, file_to_folder_id[file]),
                callback))
            for file in all_images
        ]

        self.import_tasks.update(tasks)
        [t.add_done_callback(self.import_tasks.discard) for t in tasks]
        return len(all_images)

    def compute_image(self, callback, image_path: str = None, image: Image = None):
        if not image_path and not image:
            raise ValueError('Must give image path or bytes to compute ML vectors')
        self.total_compute += 1
        task = asyncio.create_task(self.wrap_compute(self.executor.submit(compute_image, image_path), callback))
        self.compute_tasks.add(task)
        task.add_done_callback(self.compute_tasks.discard)

    async def wrap_import(self, future, callback):
        task = asyncio.wrap_future(future)
        res = await task
        self.current_import += 1
        await callback(*res)

    async def wrap_compute(self, future, callback):
        task = asyncio.wrap_future(future)
        res = await task
        self.current_computed += 1
        await callback(*res)
        # this was the last callback
        if len(self.compute_tasks) == 1:
            await self._final_callback()

    def set_final_callback(self, fn: Callable):
        self._final_callback = fn
        return fn

def compute_image(image_path: str = None, image: Image = None):
    if not image_path and not image:
        raise ValueError('Must give image path or bytes to compute ML vectors')
    if image_path:
        image = Image.open(image_path)
    image = image.convert('RGB')

    ahash = compute.to_average_hash(image)
    # TODO: find a way to access all the images for PCA
    vector = compute.to_vector(image)

    return ahash, vector


def import_image(file_path, folder_id):
    image = Image.open(file_path)
    name = file_path.split(os.sep)[-1]
    extension = name.split('.')[-1]
    width, height = image.size
    sha1_hash = hashlib.sha1(image.tobytes()).hexdigest()
    # TODO: gérer l'url statique quand on sera en mode serveur
    # url = os.path.join('/static/' + file_path.split(os.getenv('PANOPTIC_ROOT'))[1].replace('\\', '/'))
    url = f"/images/{file_path}"
    return image, folder_id, name, extension, width, height, sha1_hash, url, file_path


async def compute_folder_structure(root_path, all_files: List[str]):
    offset = len(root_path)
    root, root_name = os.path.split(root_path)
    root_folder = await db.add_folder(root_path, root_name)
    file_to_folder_id = {}
    for file in all_files:
        path, name = os.path.split(file)
        if offset == len(path):
            file_to_folder_id[file] = root_folder.id
            continue
        path = path[offset + 1:]
        parts = Path(path).parts
        current_folder = root_folder
        for part in parts:
            if part not in current_folder.children:
                child = await db.add_folder(current_folder.path + '/' + part, part, current_folder.id)
                current_folder.children[part] = child
            else:
                child = current_folder.children[part]
            file_to_folder_id[file] = child.id
            current_folder = child
    return root_folder, file_to_folder_id


async def recursive_save_folder(folder: Folder):
    # print('save: ', Folder)
    f = await db.add_folder(folder.path, folder.name, folder.parent)
    for child in folder.children.values():
        child.parent = f.id
        await recursive_save_folder(child)
