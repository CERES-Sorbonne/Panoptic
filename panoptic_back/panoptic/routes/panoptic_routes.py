import glob
import os
import pathlib
import subprocess
import sys

import psutil
from fastapi import APIRouter
from pydantic import BaseModel

from panoptic import __version__ as panoptic_version
from panoptic.core.panoptic import Panoptic
from panoptic.core.plugin import add_plugin_from_git
from panoptic.models import AddPluginPayload, IgnoredPluginPayload

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
        'projects': panoptic.data.projects,
        'ignoredPlugins': panoptic.data.ignored_plugins
    }


@selection_router.post('/ignored_plugin')
async def update_ignored_plugins(data: IgnoredPluginPayload):
    return await panoptic.set_ignored_plugin(data.project, data.plugin, data.value)


@selection_router.post("/load")
async def load_project_route(path: AddPluginPayload):
    await panoptic.load_project(path.path)
    return await get_status_route()


@selection_router.post("/close")
async def close_project():
    await panoptic.close_project()
    return await get_status_route()


@selection_router.post("/delete_project")
async def delete_project_route(req: AddPluginPayload):
    panoptic.remove_project(req.path)
    return await get_status_route()


@selection_router.post("/create_project")
async def create_project_route(req: ProjectRequest):
    await panoptic.create_project(req.name, req.path)
    return await get_status_route()


@selection_router.post("/import_project")
async def import_project_route(req: AddPluginPayload):
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
    return {"count": count_contents(path), "path": path}


@selection_router.get('/plugins')
async def get_plugins_route():
    return panoptic.get_plugin_paths()


@selection_router.post('/plugins')
async def add_plugins_route(payload: AddPluginPayload):
    # TODO: add github parameter
    path = payload.path
    if payload.git_url:
        path = add_plugin_from_git(payload.git_url, payload.plugin_name)
    return panoptic.add_plugin_path(path, payload.plugin_name, payload.git_url)


@selection_router.post('/plugin/update')
async def update_plugin_route(payload: AddPluginPayload):
    path = payload.path
    if payload.git_url:
        path = add_plugin_from_git(payload.git_url, payload.plugin_name)
    panoptic.update_plugin(path)
    return True


@selection_router.delete('/plugins')
async def del_plugins_route(path: str):
    return panoptic.del_plugin_path(path)


@selection_router.get('/version')
async def get_version_route():
    return panoptic_version

@selection_router.get('/packages')
async def get_packages_route():
    res = {
        'python': sys.version.split(' ')[0],
        'panopticPackages': {},
        'pluginPackages': {},
        'panoptic': panoptic_version,
        'platform': sys.platform
    }
    base_packages = ['numpy', 'pandas', 'pydantic']
    plugin_packages = ['torch', 'faiss-cpu', 'scikit-learn']
    base_package_versions = subprocess.check_output([sys.executable, '-m', 'pip', 'show', *base_packages])
    plugin_packages_versions = subprocess.check_output([sys.executable, '-m', 'pip', 'show', *plugin_packages])
    base_package_versions = [v.split(os.linesep.encode())[0].strip().decode() for v in base_package_versions.split(b'Version:')[1:]]
    plugin_packages_versions = [v.split(os.linesep.encode())[0].strip().decode() for v in plugin_packages_versions.split(b'Version:')[1:]]

    for index, base_package in enumerate(base_packages):
        res['panopticPackages'][base_package] = base_package_versions[index]
    if len(plugin_packages) > 0:
        for index, base_package in enumerate(plugin_packages):
            res['pluginPackages'][base_package] = plugin_packages_versions[index]
    return res

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

    if os.getenv('IS_DOCKER', False):
        mounted.append({
            'path': '/data',
            'name': '/data',
            'images': 0
        })
        mounted.append({
            'path': '/',
            'name': '/',
            'images': 0
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
