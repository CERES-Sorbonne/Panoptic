import hashlib
import io
import os

from PIL import Image
from imagehash import average_hash

from panoptic.core.task.task import Task
from panoptic.models import DbCommit, Instance, ProjectSettings

# PIL format to MIME type mapping
format_to_mime = {
    'JPEG': 'image/jpeg',
    'PNG': 'image/png',
    'GIF': 'image/gif',
    'WEBP': 'image/webp',
    'BMP': 'image/bmp',
    'TIFF': 'image/tiff',
    'ICO': 'image/vnd.microsoft.icon'
}

class ImportInstanceTask(Task):
    def __init__(self, seq: int, file: str, folder_id: int):
        super().__init__(priority=True)
        self.file = file
        self.folder_id = folder_id
        self.name = 'Import Instance'
        self.key += '-' + str(seq)

    async def run(self):
        db = self._project.db

        name = self.file.split(os.sep)[-1]
        extension = name.split('.')[-1]
        folder_id = self.folder_id

        db_image = await db.has_file(folder_id, name, extension)
        if db_image:
            db.on_import_instance.emit(db_image)
            return db_image

        sha1, width, height, ahash, large, medium, small, raw_file, mime_type = await self.run_async(self._import_image,
                                                                                                     self.file,
                                                                                                     self._project.settings)
        if not await db.has_image(sha1):
            await db.import_image(sha1, small, medium, large)

        if self._project.settings.save_file_raw:
            await db.import_raw_image(sha1, mime_type, raw_file)

        instance = Instance(-1, folder_id, name, extension, sha1, self.file, height, width, str(ahash))

        commit = DbCommit(instances=[instance])
        await self._project.db.apply_commit(commit)
        self._project.sha1_to_files[sha1].append(self.file)
        self._project.ui.commits.append(commit)
        db.on_import_instance.emit(commit.instances[0])
        return commit.instances[0]

    async def run_if_last(self):
        pass
        # self._project.ui.update_counter.image += 1

    @staticmethod
    def _import_image(file_path, settings: ProjectSettings):
        image = Image.open(file_path)
        width, height = image.size

        format_ = image.format  # e.g., 'JPEG'
        mime_type = format_to_mime[format_]

        medium_bytes = bytes()
        small_bytes = bytes()

        raw_file = bytes()
        raw_buffer = io.BytesIO()
        if settings.save_file_raw:
            image.save(raw_buffer, format=image.format)
            raw_file = raw_buffer.getvalue()

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

        return sha1_hash, width, height, ahash, large_bytes, medium_bytes, small_bytes, raw_file, mime_type
