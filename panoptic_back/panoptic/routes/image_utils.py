from sys import platform

import aiofiles.os
from starlette.responses import FileResponse, Response

from panoptic.core.project.project import Project


async def get_image_small(project: Project, sha1: str):
    image = await project.db.get_small_image(sha1)
    if image:
        # print('small')
        return Response(image, media_type="image/jpeg")
    return None


async def get_image_medium(project: Project, sha1: str):
    image = await project.db.get_medium_image(sha1)
    if image:
        # print('medium')
        return Response(image, media_type="image/jpeg")
    return None


async def get_image_large(project: Project, sha1: str):
    image = await project.db.get_large_image(sha1)
    if image:
        # print('large')
        return Response(image, media_type="image/jpeg")
    return None


async def get_image_raw(project: Project, sha1: str):
    if not project.sha1_to_files[sha1]:
        return None
    file_path = project.sha1_to_files[sha1][0]
    if platform == "linux" or platform == "linux2" or platform == "darwin":
        if not file_path.startswith('/'):
            file_path = '/' + file_path
    if await aiofiles.os.path.exists(file_path):
        # print('raw')
        return FileResponse(path=file_path)
    return None


raw_order = [get_image_raw, get_image_large, get_image_medium, get_image_small]
large_order = [get_image_large, get_image_raw, get_image_medium, get_image_small]
medium_order = [get_image_medium, get_image_large, get_image_raw, get_image_small]
small_order = raw_order[::-1]
