from __future__ import annotations

import io
from typing import TYPE_CHECKING

from PIL import Image

from panoptic.models import ProjectSettings

if TYPE_CHECKING:
    from panoptic.core.project.project import Project

from panoptic.core.task.task import Task


class ImportImageTask(Task):
    def __init__(self, project: Project, sha1: str):
        super().__init__(priority=True)
        self.project = project
        self.db = project.db
        self.sha1 = sha1
        self.name = 'Import Image Miniature'

    async def run(self):
        image_file = self.project.sha1_to_files[self.sha1][0]
        large, medium, small = await self._async(self._import_image, image_file, self.project.settings)
        await self.project.db.import_image(self.sha1, small, medium, large)

    async def run_if_last(self):
        pass

    @staticmethod
    def _import_image(file_path, settings: ProjectSettings):
        image = Image.open(file_path)
        width, height = image.size

        large_bytes = bytes()
        medium_bytes = bytes()
        small_bytes = bytes()

        image = image.convert('RGB')

        large_size = settings.image_large_size
        if settings.save_image_large and (width > large_size or height > large_size):
            image.thumbnail(size=(large_size, large_size))
            large_io = io.BytesIO()
            image.save(large_io, format='jpeg', quality=30)
            large_bytes = large_io.getvalue()

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

        del image

        return large_bytes, medium_bytes, small_bytes
