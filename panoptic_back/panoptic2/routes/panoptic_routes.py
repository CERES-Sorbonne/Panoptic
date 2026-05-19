"""Panoptic-level routes — project/plugin registry and filesystem helpers."""
from __future__ import annotations

import glob
import os
import pathlib
import subprocess
import sys
from sys import platform

import msgspec
import psutil
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import FileResponse, Response

from panoptic2.routes.deps import get_panoptic, get_server, set_dependencies   # re-export

panoptic_router = APIRouter()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _json(obj) -> Response:
    return Response(msgspec.json.encode(obj), media_type='application/json')


# ---------------------------------------------------------------------------
# Panoptic state
# ---------------------------------------------------------------------------

@panoptic_router.get('/panoptic_state')
def get_panoptic_state():
    return _json(get_panoptic().get_state())


# ---------------------------------------------------------------------------
# Project management
# ---------------------------------------------------------------------------

class ProjectCreateRequest(BaseModel):
    name: str
    path: str

class ProjectImportRequest(BaseModel):
    path: str

class ProjectUpdateRequest(BaseModel):
    id: str
    name: str | None = None
    excluded_plugins: list[str] | None = None

class ProjectDeleteRequest(BaseModel):
    id: str
    delete_files: bool = False

class ProjectLoadRequest(BaseModel):
    id: str

class ProjectCloseRequest(BaseModel):
    id: str


@panoptic_router.post('/create_project')
async def create_project_route(req: ProjectCreateRequest, request: Request):
    connection_id = request.query_params.get('connection_id')
    try:
        key = get_panoptic().create_project(req.name, req.path)
    except ValueError as e:
        raise HTTPException(400, str(e))
    await get_server()._load_project(key.id, connection_id)
    return _json(get_panoptic().get_state())


@panoptic_router.post('/import_project')
async def import_project_route(req: ProjectImportRequest, request: Request):
    connection_id = request.query_params.get('connection_id')
    try:
        key = get_panoptic().import_project(req.path)
    except ValueError as e:
        raise HTTPException(400, str(e))
    await get_server()._load_project(key.id, connection_id)
    return _json(get_panoptic().get_state())


@panoptic_router.post('/load')
async def load_project_route(req: ProjectLoadRequest, request: Request):
    connection_id = request.query_params.get('connection_id')
    try:
        await get_server()._load_project(req.id, connection_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _json(get_panoptic().get_state())


@panoptic_router.post('/close')
async def close_project_route(req: ProjectCloseRequest, request: Request):
    connection_id = request.query_params.get('connection_id')
    await get_server()._close_project(req.id, connection_id)
    return _json(get_panoptic().get_state())


@panoptic_router.post('/update_project')
def update_project_route(req: ProjectUpdateRequest):
    try:
        get_panoptic().update_project(req.id, name=req.name, excluded_plugins=req.excluded_plugins)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _json(get_panoptic().get_state())


@panoptic_router.post('/delete_project')
async def delete_project_route(req: ProjectDeleteRequest):
    get_panoptic().delete_project(req.id, delete_files=req.delete_files)
    return _json(get_panoptic().get_state())


# ---------------------------------------------------------------------------
# Plugin management
# ---------------------------------------------------------------------------

class AddPluginRequest(BaseModel):
    name: str
    source: str
    source_type: str  # 'pip' | 'git' | 'path'

class DeletePluginRequest(BaseModel):
    plugin_id: str


@panoptic_router.get('/plugins')
def get_plugins_route():
    return _json(get_panoptic().get_plugins())


@panoptic_router.post('/plugins')
def add_plugin_route(req: AddPluginRequest):
    try:
        key = get_panoptic().add_plugin(req.name, req.source, req.source_type)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _json(key)


@panoptic_router.post('/plugin/update')
def update_plugin_route(req: DeletePluginRequest):
    try:
        get_panoptic().reinstall_plugin(req.plugin_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _json(get_panoptic().get_plugins())


@panoptic_router.delete('/plugins')
def del_plugin_route(plugin_id: str):
    get_panoptic().delete_plugin(plugin_id)
    return _json(get_panoptic().get_plugins())


# ---------------------------------------------------------------------------
# Image file serving  (raw file path, no project context)
# ---------------------------------------------------------------------------

@panoptic_router.get('/images/{file_path:path}')
def get_image_file(file_path: str):
    if platform in ('linux', 'linux2', 'darwin') and not file_path.startswith('/'):
        file_path = '/' + file_path
    return FileResponse(path=file_path)


# ---------------------------------------------------------------------------
# Filesystem browser
# ---------------------------------------------------------------------------

def _images_in_folder(folder_path: str) -> list[str]:
    types = ('*.jpg', '*.jpeg', '*.png', '*.gif', '*.bmp')
    files = []
    for t in types:
        files.extend(glob.glob(os.path.join(folder_path, t)))
    return files


def _list_contents(full_path: str = '/') -> dict:
    paths = [
        os.path.join(full_path, p) if full_path != '/' else full_path + p
        for p in os.listdir(full_path)
    ]
    directories = [
        {
            'path': p,
            'name': pathlib.Path(p).name,
            'images': len(_images_in_folder(p)),
            'isProject': os.path.exists(os.path.join(p, 'project.db')),
        }
        for p in paths if os.path.isdir(p)
    ]
    return {'images': _images_in_folder(full_path)[:40], 'directories': directories}


@panoptic_router.get('/filesystem/ls/{path:path}')
def filesystem_ls(path: str = ''):
    if platform in ('linux', 'linux2', 'darwin') and not path.startswith('/'):
        path = '/' + path
    return _list_contents(path)


@panoptic_router.get('/filesystem/info')
def filesystem_info():
    partitions = [
        p for p in psutil.disk_partitions()
        if not p.mountpoint.startswith('/System')
    ]
    mounted = [
        {'path': p.mountpoint, 'name': p.mountpoint, 'images': len(_images_in_folder(p.mountpoint))}
        for p in partitions
    ]
    home = str(pathlib.Path.home())
    fast = [{'path': home, 'name': 'Home', 'images': len(_images_in_folder(home))}]
    home_dirs = _list_contents(home)['directories']
    fast.extend(d for d in home_dirs if d['name'] in ('Documents', 'Downloads', 'Desktop', 'Images', 'Pictures'))
    return {'partitions': mounted, 'fast': fast}


@panoptic_router.get('/filesystem/count/{path:path}')
def filesystem_count(path: str = ''):
    if platform in ('linux', 'linux2', 'darwin') and not path.startswith('/'):
        path = '/' + path
    folder = os.path.normpath(path)
    count = sum(
        1 for _, _, files in os.walk(folder)
        for f in files if f.lower().endswith(('.png', '.jpg', '.jpeg'))
    )
    return {'count': count, 'path': path}


# ---------------------------------------------------------------------------
# Packages info
# ---------------------------------------------------------------------------

@panoptic_router.get('/packages')
def get_packages():
    base_packages   = ['numpy', 'polars', 'pydantic']
    plugin_packages = ['torch', 'faiss-cpu', 'scikit-learn', 'transformers', 'panopticml']
    res = {
        'python': sys.version.split(' ')[0],
        'panopticPackages': {},
        'pluginPackages': {},
        'platform': sys.platform,
    }
    for pkg_list, key in [(base_packages, 'panopticPackages'), (plugin_packages, 'pluginPackages')]:
        try:
            raw = subprocess.check_output([sys.executable, '-m', 'pip', 'show', *pkg_list])
            versions = [v.split(os.linesep.encode())[0].strip().decode() for v in raw.split(b'Version:')[1:]]
            for pkg, ver in zip(pkg_list, versions):
                res[key][pkg] = ver
        except Exception:
            pass
    return res
