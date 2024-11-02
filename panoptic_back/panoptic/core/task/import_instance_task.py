from __future__ import annotations

import hashlib
import io
import os
from typing import TYPE_CHECKING

from PIL import Image
from imagehash import average_hash

from panoptic.models import DbCommit, Instance, ProjectSettings

if TYPE_CHECKING:
    from panoptic.core.project.project import Project

from panoptic.core.task.task import Task


class ImportInstanceTask(Task):
    def __init__(self, project: Project, file: str, folder_id: int):
        super().__init__(priority=True)
        self.project = project
        self.db = project.db
        self.file = file
        self.folder_id = folder_id
        self.name = 'Import Instance'

    async def run(self):
        name = self.file.split(os.sep)[-1]
        extension = name.split('.')[-1]
        folder_id = self.folder_id

        raw_db = self.db.get_raw_db()

        db_image = await raw_db.has_file(folder_id, name, extension)
        if db_image:
            self.db.on_import_instance.emit(db_image)
            return db_image

        sha1, width, height, ahash, large, medium, small = await self._async(self._import_image, self.file,
                                                                             self.project.settings)
        if not await self.db.has_image(sha1):
            await self.db.import_image(sha1, small, medium, large)
        instance = Instance(-1, folder_id, name, extension, sha1, self.file, height, width, str(ahash))

        commit = DbCommit(instances=[instance])
        await self.project.db.apply_commit(commit)
        self.project.sha1_to_files[sha1].append(self.file)
        self.project.ui.commits.append(commit)
        self.db.on_import_instance.emit(commit.instances[0])
        return commit.instances[0]

    async def run_if_last(self):
        pass
        # self.project.ui.update_counter.image += 1

    @staticmethod
    def _import_image(file_path, settings: ProjectSettings):
        image = Image.open(file_path)
        width, height = image.size

        medium_bytes = bytes()
        small_bytes = bytes()

        large_size = settings.image_large_size
        if width > large_size or height > large_size:
            image.thumbnail(size=(large_size, large_size))
        image = image.convert('RGB')

        large_io = io.BytesIO()
        image.save(large_io, format='jpeg', quality=30)
        large_bytes = large_io.getvalue()

        sha1_hash = hashlib.sha1(large_bytes).hexdigest()
        ahash = average_hash(image)

        medium_size = settings.image_medium_size
        if settings.save_image_medium and (width > medium_size or height > medium_size):
            image.thumbnail(size=(medium_size, medium_size))
            medium_io = io.BytesIO()
            image.save(medium_io, format='jpeg', quality=30)
            medium_bytes = medium_io.getvalue()

        small_size = settings.image_small_size
        if settings.save_image_small and (width > small_size or height > small_size):
            image.thumbnail(size=(small_size, small_size))
            small_io = io.BytesIO()
            image.save(small_io, format='jpeg', quality=30)
            small_bytes = small_io.getvalue()

        if not settings.save_image_large:
            large_bytes = bytes()

        del image

        return sha1_hash, width, height, ahash, large_bytes, medium_bytes, small_bytes
