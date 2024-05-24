from __future__ import annotations
import hashlib
import os
from typing import TYPE_CHECKING

import numpy
from PIL import Image
from imagehash import MeanFunc, ImageHash, ANTIALIAS

from panoptic.models import DbCommit, Instance

if TYPE_CHECKING:
    from panoptic.core.project.project import Project

from panoptic.core.task.task import Task


def average_hash(image: Image.Image, hash_size: int = 8, mean: MeanFunc = numpy.mean) -> ImageHash:
    """
	Average Hash computation

	Implementation follows http://www.hackerfactor.com/blog/index.php?/archives/432-Looks-Like-It.html

	Step by step explanation: https://web.archive.org/web/20171112054354/https://www.safaribooksonline.com/blog/2013/11/26/image-hashing-with-python/ # noqa: E501

	@image must be a PIL instance.
	@mean how to determine the average luminescence. can try numpy.median instead.
    """
    if hash_size < 2:
        raise ValueError('Hash size must be greater than or equal to 2')

    # reduce size and complexity, then covert to grayscale
    image = image.convert('L').resize((hash_size, hash_size), ANTIALIAS)

    # find average pixel value; 'pixels' is an array of the pixel values, ranging from 0 (black) to 255 (white)
    pixels = numpy.asarray(image)
    avg = mean(pixels)

    # create string of bits
    diff = pixels > avg
    # make a hash
    return ImageHash(diff)


class ImportInstanceTask(Task):
    def __init__(self, project: Project, file: str, folder_id: int):
        super().__init__(priority=True)
        self.project = project
        self.db = project.db
        self.file = file
        self.folder_id = folder_id
        self.name = 'Import Image'

    async def run(self):
        name = self.file.split(os.sep)[-1]
        extension = name.split('.')[-1]
        folder_id = self.folder_id

        raw_db = self.db.get_raw_db()

        db_image = await raw_db.has_file(folder_id, name, extension)
        if db_image:
            self.db.on_import_instance.emit(db_image)
            return db_image

        sha1, url, width, height, ahash = await self._async(self._import_image, self.file, raw_db.get_project_path())
        instance = Instance(-1, folder_id, name, extension, sha1, url, height, width, str(ahash))

        commit = DbCommit(instances=[instance])
        await self.project.db.apply_commit(commit)
        self.project.ui.commits.append(commit)
        self.db.on_import_instance.emit(commit.instances[0])
        return commit.instances[0]

    async def run_if_last(self):
        pass
        # self.project.ui.update_counter.image += 1

    @staticmethod
    def _import_image(file_path, project_path: str):
        image = Image.open(file_path)
        width, height = image.size
        sha1_hash = hashlib.sha1(image.tobytes()).hexdigest()
        # TODO: gérer l'url statique quand on sera en mode serveur
        # url = os.path.join('/static/' + global_file_path.split(os.getenv('PANOPTIC_ROOT'))[1].replace('\\', '/'))
        if not os.path.exists(os.path.join(project_path, "mini")):
            os.mkdir(os.path.join(project_path, "mini"))
        url = file_path
        image = image.convert('RGB')
        mini = image.copy()
        mini.thumbnail(size=(200, 200))
        mini.save(os.path.join(project_path, "mini", sha1_hash + '.jpeg'), optimize=True, quality=30)

        ahash = average_hash(image)

        del image
        del mini
        # gc.collect()

        return sha1_hash, url, width, height, ahash
