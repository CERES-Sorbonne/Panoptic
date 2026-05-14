"""Project-level routes — prefixed /projects/{project_uid}."""
from __future__ import annotations

import logging
import orjson
from sys import platform

import msgspec
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse

from panoptic.models.data import (
    Commit, DeleteCommit, Folder, Instance, Property, Sha1Value,
    Tag, InstanceValue, UpsertCommit,
)
from panoptic2.core.project.project import Project2
from panoptic2.models.action_models import ActionContext
from panoptic2.routes.deps import get_project

project_router = APIRouter(prefix='/projects/{project_uid}')

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _json(obj) -> Response:
    return Response(msgspec.json.encode(obj), media_type='application/json')


def _dep(project_uid: str) -> Project2:
    return get_project(project_uid)


# ---------------------------------------------------------------------------
# State — initial full load (ndjson stream)
# ---------------------------------------------------------------------------

@project_router.get('/db_state_stream')
def stream_db_state(project: Project2 = Depends(_dep)):
    """Stream full project state as newline-delimited JSON chunks."""
    def _generate():
        # Each chunk: { "type": "...", "data": [...] }
        for entity_type, getter in [
            ('properties',      project.get_properties),
            ('tags',            project.get_tags),
            ('folders',         project.get_folders),
            ('files',           project.get_files),
            ('instances',       project.get_instances),
            ('instance_values', project.get_instance_values),
            ('sha1_values',     project.get_sha1_values),
        ]:
            try:
                items = getter()
                chunk = {'type': entity_type, 'data': msgspec.to_builtins(items)}
                yield orjson.dumps(chunk) + b'\n'
            except Exception:
                logger.exception(f'db_state_stream: error loading {entity_type}')
        yield orjson.dumps({'type': 'done'}) + b'\n'

    return StreamingResponse(_generate(), media_type='application/x-ndjson')


@project_router.get('/db_state')
def get_db_state(project: Project2 = Depends(_dep)):
    return _json({
        'properties':      project.get_properties(),
        'tags':            project.get_tags(),
        'folders':         project.get_folders(),
        'files':           project.get_files(),
        'instances':       project.get_instances(),
        'instance_values': project.get_instance_values(),
        'sha1_values':     project.get_sha1_values(),
    })


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------

@project_router.get('/property')
def get_properties(project: Project2 = Depends(_dep)):
    return _json(project.get_properties())


@project_router.get('/tags')
def get_tags(project: Project2 = Depends(_dep)):
    return _json(project.get_tags())


@project_router.get('/folders')
def get_folders(project: Project2 = Depends(_dep)):
    return _json(project.get_folders())


@project_router.get('/instances')
def get_instances(project: Project2 = Depends(_dep)):
    return _json(project.get_instances())


# ---------------------------------------------------------------------------
# Commits  (write / undo / redo)
# ---------------------------------------------------------------------------

@project_router.post('/commit/upsert')
async def upsert_commit_route(request: Request, project: Project2 = Depends(_dep)):
    body = await request.body()
    try:
        commit_data = msgspec.json.decode(body, type=UpsertCommit)
    except Exception as e:
        raise HTTPException(400, f'Invalid UpsertCommit: {e}')
    commit = project.apply_upsert_commit('ui', commit_data)
    return _json(commit)


@project_router.post('/commit/delete')
async def delete_commit_route(request: Request, project: Project2 = Depends(_dep)):
    body = await request.body()
    try:
        commit_data = msgspec.json.decode(body, type=DeleteCommit)
    except Exception as e:
        raise HTTPException(400, f'Invalid DeleteCommit: {e}')
    commit = project.apply_delete_commit('ui', commit_data)
    return _json(commit)


@project_router.post('/undo')
def undo_route(project: Project2 = Depends(_dep)):
    commits = project.get_commits()
    active = [c for c in commits if c.active]
    if not active:
        raise HTTPException(400, 'Nothing to undo')
    last = max(active, key=lambda c: c.id)
    project.set_commit_active(last.id, False)
    return _json(last)


@project_router.post('/redo')
def redo_route(project: Project2 = Depends(_dep)):
    commits = project.get_commits()
    inactive = [c for c in commits if not c.active]
    if not inactive:
        raise HTTPException(400, 'Nothing to redo')
    last = max(inactive, key=lambda c: c.id)
    project.set_commit_active(last.id, True)
    return _json(last)


@project_router.get('/history')
def get_history(project: Project2 = Depends(_dep)):
    commits = project.get_commits()
    undo = [c for c in commits if c.active]
    redo = [c for c in commits if not c.active]
    return {'undo': len(undo), 'redo': len(redo)}


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------

def _get_image_bytes(project: Project2, sha1: str, type_id: int) -> bytes | None:
    images = project.get_images(type_id=type_id, sha1=sha1)
    return images[0].data if images else None


@project_router.get('/image/small/{sha1:path}')
def get_image_small(sha1: str, project: Project2 = Depends(_dep)):
    data = _get_image_bytes(project, sha1, type_id=1)
    if data:
        return Response(data, media_type='image/jpeg')
    # fall back to large
    data = _get_image_bytes(project, sha1, type_id=2)
    if data:
        return Response(data, media_type='image/jpeg')
    raise HTTPException(404, f'Image {sha1} not found')


@project_router.get('/image/large/{sha1:path}')
def get_image_large(sha1: str, project: Project2 = Depends(_dep)):
    data = _get_image_bytes(project, sha1, type_id=2)
    if data:
        return Response(data, media_type='image/jpeg')
    data = _get_image_bytes(project, sha1, type_id=1)
    if data:
        return Response(data, media_type='image/jpeg')
    raise HTTPException(404, f'Image {sha1} not found')


@project_router.get('/image/raw/{sha1:path}')
def get_image_raw(sha1: str, project: Project2 = Depends(_dep)):
    from pathlib import Path
    from starlette.responses import FileResponse as FR
    # Instance → File to find original path on disk
    for inst in project.get_instances():
        if inst.sha1 != sha1:
            continue
        for f in project.get_files():
            if f.id == inst.file_id and f.name and Path(f.name).exists():
                return FR(f.name)
        break
    # Fall back to largest stored thumbnail
    return get_image_large(sha1, project)


@project_router.get('/image/medium/{sha1:path}')
def get_image_medium(sha1: str, project: Project2 = Depends(_dep)):
    return get_image_large(sha1, project)


# ---------------------------------------------------------------------------
# Actions & plugins
# ---------------------------------------------------------------------------

class ExecuteActionRequest(BaseModel):
    function: str
    instance_ids: list[int] | None = None
    group_name: str | None = None
    ui_inputs: dict = {}


@project_router.post('/action_execute')
def execute_action(req: ExecuteActionRequest, project: Project2 = Depends(_dep)):
    ctx = ActionContext(
        instance_ids=req.instance_ids,
        group_name=req.group_name,
        ui_inputs=req.ui_inputs,
    )
    try:
        result = project.action.call(req.function, ctx)
    except KeyError:
        raise HTTPException(404, f'Action {req.function!r} not found')
    except Exception as e:
        raise HTTPException(500, str(e))
    return result  # ActionResult is a dataclass — FastAPI serialises it


@project_router.get('/actions')
def get_actions(project: Project2 = Depends(_dep)):
    return project.action.get_all()


@project_router.get('/plugins_info')
def get_plugins_info(project: Project2 = Depends(_dep)):
    return [p.get_description() for p in project.plugins]


# ---------------------------------------------------------------------------
# UI data  (tab state / user defaults)
# ---------------------------------------------------------------------------

class UiDataRequest(BaseModel):
    key: str
    data: object


@project_router.get('/ui_data/{key:path}')
def get_ui_data(key: str, project: Project2 = Depends(_dep), user_id: str = 'default'):
    result = project.get_user_defaults(user_id=user_id, key=key)
    return result.data if result else None


@project_router.post('/ui_data')
def set_ui_data(req: UiDataRequest, project: Project2 = Depends(_dep), user_id: str = 'default'):
    from panoptic.core.databases.project.models import UserDefaults
    project.set_user_defaults(UserDefaults(user_id=user_id, key=req.key, data=req.data))
    return {'ok': True}


# ---------------------------------------------------------------------------
# Media — maps and atlases
# ---------------------------------------------------------------------------

@project_router.get('/list_maps')
def list_maps(project: Project2 = Depends(_dep)):
    return _json(project.get_maps())


@project_router.get('/map/{map_id}')
def get_map(map_id: int, project: Project2 = Depends(_dep)):
    maps = project.get_maps(id=map_id)
    if not maps:
        raise HTTPException(404, f'Map {map_id} not found')
    return _json(maps[0])


@project_router.delete('/map')
def delete_map(map_id: int, project: Project2 = Depends(_dep)):
    project.delete_map(map_id)
    return {'ok': True}


@project_router.get('/atlas/{atlas_id}')
def get_atlas(atlas_id: int, project: Project2 = Depends(_dep)):
    atlases = project.get_image_atlases(id=atlas_id)
    if not atlases:
        raise HTTPException(404, f'Atlas {atlas_id} not found')
    return _json(atlases[0])


@project_router.get('/vector_types')
def get_vector_types(project: Project2 = Depends(_dep)):
    return _json(project.get_vector_types())


# ---------------------------------------------------------------------------
# Not-yet-ported routes — return 501 so the UI fails gracefully
# ---------------------------------------------------------------------------

@project_router.post('/import/upload')
async def import_upload_stub(): raise HTTPException(501, 'Import not yet implemented in panoptic2')

@project_router.post('/import/parse')
async def import_parse_stub(): raise HTTPException(501, 'Import not yet implemented in panoptic2')

@project_router.post('/import/confirm')
async def import_confirm_stub(): raise HTTPException(501, 'Import not yet implemented in panoptic2')

@project_router.post('/import/tags')
async def import_tags_stub(): raise HTTPException(501, 'Import not yet implemented in panoptic2')

@project_router.post('/export')
async def export_stub(): raise HTTPException(501, 'Export not yet implemented in panoptic2')

@project_router.get('/settings')
async def get_settings_stub(): raise HTTPException(501, 'Settings not yet implemented in panoptic2')

@project_router.post('/settings')
async def post_settings_stub(): raise HTTPException(501, 'Settings not yet implemented in panoptic2')
