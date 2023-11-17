import asyncio
import os
from concurrent.futures import Executor
from pathlib import Path
from typing import List

from panoptic.core import db
from panoptic.core.process_queue import ImportImageQueue, ComputeVectorsQueue
from panoptic.models import Folder, ImageImportTask, Image, ComputedValue
from panoptic.scripts.create_faiss_index import compute_faiss_index


class ImageImporter:
    def __init__(self, executor: Executor):
        self.status = 'read'
        self.executor = executor

        self.total_import = 0
        self.current_import = 0

        self.total_compute = 0
        self.current_computed = 0

        # self._final_callback = None

        self._import_queue = ImportImageQueue(executor)
        self._compute_queue = ComputeVectorsQueue(executor)
        self._pca_task: asyncio.Task | None = None
        self._auto_pca = False

        self._new_images = []
    # def _reset_counters(self):
    #     self.total_import = -1
    #     self.current_import = 0

    def import_done(self):
        return self._import_queue.done()

    def get_new_images(self):
        copy = [id_ for id_ in self._new_images]
        self._new_images.clear()
        return copy

    async def import_folder(self, folder: str):
        if self.total_import == self.current_import:
            self.total_compute = 0
            self.current_computed = 0
            self.total_import = 0
            self.current_import = 0

        self._auto_pca = False

        all_files = [os.path.join(path, name) for path, subdirs, files in os.walk(folder) for name in files]
        all_images = [i for i in all_files if
                      i.lower().endswith('.png') or i.lower().endswith('.jpg') or i.lower().endswith('.jpeg')]
        self.total_import += len(all_images)
        self.total_compute += len(all_images)

        folder_node, file_to_folder_id = await compute_folder_structure(folder, all_images)

        self.status = 'compute'

        def on_import(image: Image, is_last):
            self.current_import += 1
            self._compute_queue.add_task(image.id)

            if self._import_queue.done():
                self._compute_queue.start_workers(6)

        def on_compute(vector: ComputedValue, is_last):
            self.current_computed += 1
            if is_last:
                # print('would run pca now')
                self._pca_task = asyncio.create_task(compute_faiss_index())

        self._import_queue.done_callback = on_import
        self._compute_queue.done_callback = on_compute

        tasks = [ImageImportTask(folder_id=file_to_folder_id[file], image_path=file) for file in all_images]
        [self._import_queue.add_task(t) for t in tasks]

        self._import_queue.start_workers(6)

        return len(all_images)


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
