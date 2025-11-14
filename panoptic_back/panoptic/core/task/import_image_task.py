import io

from PIL import Image

from panoptic.core.task.import_instance_task import format_to_mime
from panoptic.models import ProjectSettings

from panoptic.core.task.task import Task


class ImportImageTask(Task):
    def __init__(self, sha1: str):
        super().__init__(priority=True)
        self.sha1 = sha1
        self.name = 'Import Image Miniature'

    async def run(self):
        image_file = self._project.sha1_to_files[self.sha1][0]
        large, medium, small, raw, mime_type = await self.run_async(self._import_image, image_file,
                                                                    self._project.settings)
        await self._project.db.import_image(self.sha1, small, medium, large)
        if raw:
            await self._project.db.import_raw_image(self.sha1, mime_type, raw)

    async def run_if_last(self):
        pass

    @staticmethod
    def _import_image(file_path, settings: ProjectSettings):
        image = Image.open(file_path)
        width, height = image.size

        large_bytes = bytes()
        medium_bytes = bytes()
        small_bytes = bytes()
        raw_bytes = bytes()

        format_ = image.format  # e.g., 'JPEG'
        mime_type = format_to_mime[format_]

        if settings.save_file_raw:
            raw_buffer = io.BytesIO()
            image.save(raw_buffer, format=image.format)
            raw_bytes = raw_buffer.getvalue()

        image = image.convert('RGB')

        small_size = settings.image_small_size
        medium_size = settings.image_medium_size
        large_size = settings.image_large_size



        if settings.save_image_large and ((width > large_size or height > large_size) or ((width < large_size or height < large_size) and (width > medium_size or height > medium_size))):
            large_size = min(width, height, large_size)
            image.thumbnail(size=(large_size, large_size))
            large_io = io.BytesIO()
            image.save(large_io, format='jpeg', quality=30)
            large_bytes = large_io.getvalue()

        if settings.save_image_medium and (width > medium_size or height > medium_size):
            image.thumbnail(size=(medium_size, medium_size))
            medium_io = io.BytesIO()
            image.save(medium_io, format='jpeg', quality=30)
            medium_bytes = medium_io.getvalue()

        if settings.save_image_small and (width > small_size or height > small_size):
            image.thumbnail(size=(small_size, small_size))
            small_io = io.BytesIO()
            image.save(small_io, format='jpeg', quality=30)
            small_bytes = small_io.getvalue()

        del image

        return large_bytes, medium_bytes, small_bytes, raw_bytes, mime_type
