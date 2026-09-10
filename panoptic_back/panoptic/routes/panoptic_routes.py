"""Panoptic-level routes — project/plugin registry and filesystem helpers."""
from __future__ import annotations

import glob
import os
import pathlib
import subprocess
import sys
from sys import platform

import anyio
import msgspec
import psutil
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import FileResponse, Response

from panoptic.routes.deps import get_panoptic, get_server, set_dependencies   # re-export

panoptic_router = APIRouter()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _json(obj) -> Response:
    return Response(msgspec.json.encode(obj), media_type='application/json')


# ---------------------------------------------------------------------------
# Panoptic state — split into focused endpoints
# ---------------------------------------------------------------------------

@panoptic_router.get('/projects')
def get_projects_route():
    return _json(get_panoptic().get_projects_state())


@panoptic_router.get('/plugins')
def get_plugins_state_route():
    return _json(get_panoptic().get_plugins())


@panoptic_router.get('/users')
def get_users_route():
    return _json([msgspec.structs.asdict(u) for u in get_panoptic().get_users()])


class UserCreateRequest(BaseModel):
    name: str

class UserConnectRequest(BaseModel):
    user_id: str


@panoptic_router.post('/users')
async def create_user_route(req: UserCreateRequest):
    try:
        user = get_panoptic().create_user(req.name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    await get_server()._emit_update_users()
    return _json(msgspec.structs.asdict(user))


@panoptic_router.delete('/users/{user_id}')
async def delete_user_route(user_id: str):
    from panoptic.core.databases.panoptic.panoptic_db import DEFAULT_USER_ID
    if user_id == DEFAULT_USER_ID:
        raise HTTPException(400, "Cannot delete the default user")
    get_panoptic().delete_user(user_id)
    await get_server()._emit_update_users()
    return {}


@panoptic_router.post('/connect_user')
async def connect_user_route(req: UserConnectRequest, request: Request):
    connection_id = request.query_params.get('connection_id')
    server = get_server()
    user = next((u for u in get_panoptic().get_users() if u.id == req.user_id), None)
    if not user:
        raise HTTPException(404, "User not found")
    state = server._connection_states.get(connection_id)
    if state:
        state.user = user
    last_project = server._user_last_project.get(user.id)
    known_ids = {p.id for p in get_panoptic().db.get_projects()}
    if last_project and last_project in known_ids and (state is None or state.connected_project != last_project):
        await server._load_project(last_project, connection_id)
    else:
        await server._emit_connection_state(connection_id)
    return {}


@panoptic_router.post('/disconnect_user')
async def disconnect_user_route(request: Request):
    connection_id = request.query_params.get('connection_id')
    server = get_server()
    from panoptic.core.databases.panoptic.panoptic_db import DEFAULT_USER_ID
    default_user = next((u for u in get_panoptic().get_users() if u.id == DEFAULT_USER_ID), None)
    state = server._connection_states.get(connection_id)
    if state and default_user:
        state.user = default_user
    await server._emit_connection_state(connection_id)
    return {}


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
        key = await anyio.to_thread.run_sync(
            lambda: get_panoptic().create_project(req.name, req.path)
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    await get_server()._load_project(key.id, connection_id)
    return _json(get_panoptic().get_projects_state())


@panoptic_router.post('/import_project')
async def import_project_route(req: ProjectImportRequest, request: Request):
    connection_id = request.query_params.get('connection_id')
    try:
        key = await anyio.to_thread.run_sync(
            lambda: get_panoptic().import_project(req.path)
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    await get_server()._load_project(key.id, connection_id)
    return _json(get_panoptic().get_projects_state())


@panoptic_router.post('/load')
async def load_project_route(req: ProjectLoadRequest, request: Request):
    connection_id = request.query_params.get('connection_id')
    try:
        await get_server()._load_project(req.id, connection_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _json(get_panoptic().get_projects_state())


@panoptic_router.post('/close')
async def close_project_route(req: ProjectCloseRequest, request: Request):
    connection_id = request.query_params.get('connection_id')
    await get_server()._close_project(req.id, connection_id)
    return _json(get_panoptic().get_projects_state())


@panoptic_router.post('/update_project')
def update_project_route(req: ProjectUpdateRequest, background_tasks: BackgroundTasks):
    try:
        get_panoptic().update_project(req.id, name=req.name, excluded_plugins=req.excluded_plugins)
    except ValueError as e:
        raise HTTPException(400, str(e))
    background_tasks.add_task(get_server()._emit_update_projects)
    return _json(get_panoptic().get_projects_state())


@panoptic_router.post('/delete_project')
def delete_project_route(req: ProjectDeleteRequest, background_tasks: BackgroundTasks):
    get_panoptic().delete_project(req.id, delete_files=req.delete_files)
    background_tasks.add_task(get_server()._emit_update_projects)
    return _json(get_panoptic().get_projects_state())


# ---------------------------------------------------------------------------
# Plugin management
# ---------------------------------------------------------------------------

class AddPluginRequest(BaseModel):
    name: str
    source: str
    source_type: str  # 'pip' | 'git' | 'path'

class DeletePluginRequest(BaseModel):
    plugin_id: str


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


# ---------------------------------------------------------------------------
# Legacy (0.x) project migration
# ---------------------------------------------------------------------------

class LegacyMigrateRequest(BaseModel):
    legacyPath: str
    destPath: str
    name: str | None = None
    load: bool = False

class LegacyDismissRequest(BaseModel):
    path: str | None = None


def _legacy_scan_json(scan) -> dict:
    """camelCase — the frontend consumes these keys verbatim."""
    if scan is None:
        return {'registries': [], 'projects': [], 'skipped': False, 'reason': None, 'scanned': False}
    return {
        'scanned': True,
        'skipped': scan.skipped,
        'reason': scan.reason,
        'registries': [
            {'path': r.path, 'shape': r.shape, 'projects': r.projects,
             'plugins': r.plugins, 'problem': r.problem}
            for r in scan.registries
        ],
        'projects': [
            {'legacyPath': p.legacy_path, 'name': p.name, 'registry': p.registry,
             'shape': p.shape, 'recordedVersion': p.recorded_version,
             'instanceCount': p.instance_count, 'exists': p.exists,
             'status': p.status, 'problem': p.problem,
             'migratedTo': p.migrated_to, 'suggestedPath': p.suggested_path,
             'plugins': p.plugins, 'dbSize': p.db_size}
            for p in scan.projects
        ],
    }


def _legacy_run_json(run) -> dict:
    return {
        'id': run.id, 'legacyPath': run.legacy_path, 'destPath': run.dest_path,
        'name': run.name, 'status': run.status, 'stage': run.stage,
        'stageIndex': run.stage_index, 'stageCount': run.stage_count,
        'detail': run.detail, 'error': run.error, 'warnings': run.warnings,
        'plugins': run.plugins, 'reportPath': run.report_path,
        'projectId': run.project_id,
    }


@panoptic_router.get('/legacy/projects')
async def get_legacy_projects_route(rescan: bool = False):
    service = get_panoptic().legacy
    scan = service.scan
    if scan is None or rescan:
        scan = await anyio.to_thread.run_sync(service.discover)
    return _legacy_scan_json(scan)


@panoptic_router.post('/legacy/migrate', status_code=202)
def migrate_legacy_project_route(req: LegacyMigrateRequest):
    try:
        run = get_panoptic().legacy.migrate(
            req.legacyPath, req.destPath, req.name, load=req.load)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _legacy_run_json(run)


@panoptic_router.post('/legacy/dismiss')
async def dismiss_legacy_route(req: LegacyDismissRequest):
    scan = await anyio.to_thread.run_sync(
        lambda: get_panoptic().legacy.dismiss(req.path))
    return _legacy_scan_json(scan)


@panoptic_router.get('/legacy/report/{run_id}')
def get_legacy_report_route(run_id: str):
    run = get_panoptic().legacy.get_run(run_id)
    if not run or not run.report_path:
        raise HTTPException(404, "No report for this migration run")
    if not os.path.isfile(run.report_path):
        raise HTTPException(404, f"Report file {run.report_path} is missing")
    with open(run.report_path, encoding='utf-8') as fh:
        return Response(fh.read(), media_type='text/markdown')
