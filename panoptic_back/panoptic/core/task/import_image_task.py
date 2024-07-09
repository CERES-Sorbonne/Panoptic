from __future__ import annotations

import hashlib
import io
import os
import time
from typing import TYPE_CHECKING

from PIL import Image
from imagehash import average_hash

from panoptic.models import DbCommit, Instance

if TYPE_CHECKING:
    from panoptic.core.project.project import Project

from panoptic.core.task.task import Task

SMALL_SIZE = 128
LARGE_SIZE = 1024


class ImportInstanceTask(Task):
    def __init__(self, project: Project, file: str, folder_id: int):
        super().__init__(priority=True)
        self.project = project
        self.db = project.db
        self.file = file
        self.folder_id = folder_id
        self.name = 'Import Image'

    async def run(self):
        old = time.time()
        name = self.file.split(os.sep)[-1]
        extension = name.split('.')[-1]
        folder_id = self.folder_id

        raw_db = self.db.get_raw_db()

        db_image = await raw_db.has_file(folder_id, name, extension)
        if db_image:
            self.db.on_import_instance.emit(db_image)
            return db_image

        sha1, width, height, ahash, large, small = await self._async(self._import_image, self.file,
                                                                     raw_db.get_project_path())
        if not await self.db.has_image(sha1):
            old = time.time()
            await self.db.import_image(sha1, small, large)
            print(time.time() - old)
        instance = Instance(-1, folder_id, name, extension, sha1, self.file, height, width, str(ahash))

        commit = DbCommit(instances=[instance])
        await self.project.db.apply_commit(commit)
        self.project.ui.commits.append(commit)
        self.db.on_import_instance.emit(commit.instances[0])
        print('import task', time.time() - old)
        return commit.instances[0]

    async def run_if_last(self):
        pass
        # self.project.ui.update_counter.image += 1

    @staticmethod
    def _import_image(file_path, project_path: str):
        original_image = Image.open(file_path)
        width, height = original_image.size

        old = time.time()
        large_image = original_image
        if width > LARGE_SIZE or height > LARGE_SIZE:
            large_image = original_image.copy()
            large_image.thumbnail(size=(LARGE_SIZE, LARGE_SIZE))
        # print('large', time.time() - old)
        old = time.time()
        small_image = large_image
        if width > SMALL_SIZE or height > SMALL_SIZE:
            small_image = large_image.copy()
            small_image.thumbnail(size=(SMALL_SIZE, SMALL_SIZE))
        # print('small', time.time() - old)

        sha1_hash = hashlib.sha1(large_image.tobytes()).hexdigest()
        # print('sha1', time.time() - old)
        # TODO: gérer l'url statique quand on sera en mode serveur
        # url = os.path.join('/static/' + global_file_path.split(os.getenv('PANOPTIC_ROOT'))[1].replace('\\', '/'))
        # if not os.path.exists(os.path.join(project_path, "mini")):
        #     os.mkdir(os.path.join(project_path, "mini"))
        # image = image.convert('RGB')
        # mini = original_image.copy()
        # mini.thumbnail(size=(200, 200))
        # mini.save(os.path.join(project_path, "mini", sha1_hash + '.png'), optimize=True, quality=30)
        ahash = average_hash(large_image)
        # print('ahash', time.time() - old)
        large_bytes = io.BytesIO()
        large_image.save(large_bytes, format='jpeg', optimize=True, quality=30)
        large_bytes = large_bytes.getvalue()
        # print('large_save', time.time() - old)
        small_bytes = io.BytesIO()
        small_image.save(small_bytes, format='jpeg', optimize=True, quality=30)
        small_bytes = small_bytes.getvalue()
        # print('small_save', time.time() - old)

        del original_image
        del large_image
        del small_image
        # gc.collect()

        return sha1_hash, width, height, ahash, large_bytes, small_bytes
