import asyncio
import glob
import os
import pathlib

import psutil
from fastapi import APIRouter
from pydantic import BaseModel

from panoptic.api import PathRequest
from panoptic.core import db_utils
from panoptic.project_manager import ProjectManager

# project manager
manager = ProjectManager()
manager.load_data()

selection_router = APIRouter()


class ProjectRequest(BaseModel):
    path: str
    name: str


@selection_router.get("/status")
async def get_status_route():
    return {
        'isLoaded': db_utils.is_loaded(),
        'selectedProject': manager.panoptic_data.last_opened,
        'projects': manager.panoptic_data.projects
    }


@selection_router.post("/load")
async def load_project_route(path: PathRequest):
    print('load', path.path)
    await db_utils.load_project(path.path)
    manager.set_loaded(path.path)
    return await get_status_route()


@selection_router.post("/close")
async def close_project():
    await db_utils.close()
    manager.close()
    return await get_status_route()


@selection_router.post("/delete_project")
async def delete_project_route(req: PathRequest):
    manager.remove_project(req.path)
    return await get_status_route()


@selection_router.post("/create_project")
async def create_project_route(req: ProjectRequest):
    manager.add_project(req.name, req.path)
    return await load_project_route(PathRequest(path=req.path))


@selection_router.get("/filesystem/ls/{path:path}")
def api(path: str = ""):
    return list_contents('/' + path)


@selection_router.get('/filesystem/info')
def filesystem_info_route():
    return list_index()


def images_in_folder(folder_path):
    types = ('*.jpg', '*.jpeg', '*.png', '*.gif', '*.bmp')  # the tuple of file types
    image_files = []
    for type_ in types:
        image_files.extend(glob.glob(os.path.join(folder_path, type_)))

    return image_files


def list_contents(full_path: str = '/'):
    paths = [full_path + '/' + p if full_path != '/' else full_path + p for p in os.listdir(full_path)]
    directories = [p for p in paths if os.path.isdir(p)]
    directories = [{
        'path': p,
        'name': pathlib.Path(p).name,
        'images': len(images_in_folder(p))
    } for p in directories]
    images = images_in_folder(full_path)

    return {'images': images[0:40], 'directories': directories}


def list_disk():
    files = []
    partitions = psutil.disk_partitions()
    partitions = [p for p in partitions if not p.mountpoint.startswith("/System")]
    for partition in partitions:
        files.append({
            'path': partition.mountpoint,
            'name': pathlib.Path(partition.mountpoint).name,
            'images': len(images_in_folder(partition.mountpoint))
        })
    return files


def list_index():
    mounted = []

    partitions = psutil.disk_partitions()
    partitions = [p for p in partitions if not p.mountpoint.startswith("/System")]
    for partition in partitions:
        mounted.append({
            'path': partition.mountpoint,
            'name': partition.mountpoint,
            'images': len(images_in_folder(partition.mountpoint))
        })

    files = [{
        'path': pathlib.Path.home(),
        'name': 'Home',
        'images': len(images_in_folder(pathlib.Path.home()))
    }]

    home_files = list_contents(str(pathlib.Path.home()))['directories']
    home_files = [f for f in home_files if f['name'] in ['Documents', 'Downloads', 'Desktop', 'Images', 'Pictures']]
    files.extend(home_files)
    return {'partitions': mounted, 'fast': files}
