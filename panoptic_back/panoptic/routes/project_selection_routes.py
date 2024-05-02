import glob
import os
import pathlib

import psutil
from fastapi import APIRouter
from pydantic import BaseModel

from panoptic.core.panoptic import Panoptic
from panoptic.models import PathRequest

selection_router = APIRouter()

panoptic: Panoptic | None = None


def set_panoptic(pano: Panoptic):
    global panoptic
    panoptic = pano


class ProjectRequest(BaseModel):
    path: str
    name: str


@selection_router.get("/status")
async def get_status_route():
    return {
        'isLoaded': panoptic.is_loaded(),
        'selectedProject': panoptic.project_id,
        'projects': panoptic.data.projects
    }


@selection_router.post("/load")
async def load_project_route(path: PathRequest):
    await panoptic.load_project(path.path)
    return await get_status_route()


@selection_router.post("/close")
async def close_project():
    await panoptic.close_project()
    return await get_status_route()


@selection_router.post("/delete_project")
async def delete_project_route(req: PathRequest):
    panoptic.remove_project(req.path)
    return await get_status_route()


@selection_router.post("/create_project")
async def create_project_route(req: ProjectRequest):
    await panoptic.create_project(req.name, req.path)
    return await get_status_route()


@selection_router.post("/import_project")
async def import_project_route(req: PathRequest):
    await panoptic.import_project(req.path)
    return await get_status_route()


@selection_router.get("/filesystem/ls/{path:path}")
def api(path: str = ""):
    return list_contents(path)


@selection_router.get('/filesystem/info')
def filesystem_info_route():
    return list_index()


@selection_router.get("/filesystem/count/{path:path}")
def fs_count_route(path: str = ""):
    return {"count": count_contents(path), "path": path }


@selection_router.get('/plugins')
async def get_plugins_route():
    return panoptic.get_plugin_paths()


@selection_router.post('/plugins')
async def add_plugins_route(path: PathRequest):
    return panoptic.add_plugin_path(path.path)


@selection_router.delete('/plugins')
async def del_plugins_route(path: str):
    return panoptic.del_plugin_path(path)


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
        'images': len(images_in_folder(p)),
        'isProject': os.path.exists(os.path.join(p, 'panoptic.db'))
    } for p in directories]
    images = images_in_folder(full_path)

    return {'images': images[0:40], 'directories': directories}


def count_contents(full_path: str):
    folder = os.path.normpath(full_path)
    all_files = [os.path.join(path, name) for path, subdirs, files in os.walk(folder) for name in files]
    all_images = [i for i in all_files if
                  i.lower().endswith('.png') or i.lower().endswith('.jpg') or i.lower().endswith('.jpeg')]
    return len(all_images)


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
