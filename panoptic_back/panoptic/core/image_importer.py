import asyncio
import hashlib
import os
from concurrent.futures import ProcessPoolExecutor

from PIL import Image

from panoptic import compute


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

    # def _reset_counters(self):
    #     self.total_import = -1
    #     self.current_import = 0

    def import_folder(self, callback, folder: str):
        all_files = [os.path.join(path, name) for path, subdirs, files in os.walk(folder) for name in files]
        all_images = [i for i in all_files if
                      i.lower().endswith('.png') or i.lower().endswith('.jpg') or i.lower().endswith('.jpeg')]
        self.total_import += len(all_images)
        self.status = 'compute'
        tasks = [asyncio.create_task(self.wrap_import(self.executor.submit(import_image, i), callback)) for i in
                 all_images]
        self.import_tasks.update(tasks)
        [t.add_done_callback(self.import_tasks.discard) for t in tasks]
        return len(all_images)

    def compute_image(self, callback, image_path: str = None, image: Image = None):
        if not image_path and not image:
            raise ValueError('Must give image path or bytes to compute ML vectors')
        self.total_compute += 1
        task = asyncio.create_task(self.wrap_compute(self.executor.submit(compute_image, image_path, image), callback))
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


def import_image(file_path):
    image = Image.open(file_path)
    name = file_path.split(os.sep)[-1]
    extension = name.split('.')[-1]
    width, height = image.size
    sha1_hash = hashlib.sha1(image.tobytes()).hexdigest()
    # TODO: gérer l'url statique quand on sera en mode serveur
    # url = os.path.join('/static/' + file_path.split(os.getenv('PANOPTIC_ROOT'))[1].replace('\\', '/'))
    url = f"/images/{file_path}"
    return image, file_path, name, extension, width, height, sha1_hash, url
