import asyncio
import logging
from dataclasses import asdict, is_dataclass
from time import time
from typing import Optional

import orjson
from fastapi import APIRouter, UploadFile, Depends, HTTPException
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import FileResponse, StreamingResponse

from panoptic.core.project.project import Project
from panoptic.models import Property, VectorDescription, ExecuteActionPayload, \
    ExportPropertiesPayload, UIDataPayload, PluginParamsPayload, ImportPayload, DbCommit, CommitHistory, Update, \
    ProjectSettings, TagMergePayload, LoadState, DeleteVectorTypePayload
from panoptic.models.results import LoadResult
from panoptic.routes.image_utils import medium_order, large_order, small_order, raw_order
from panoptic.routes.panoptic_routes import get_panoptic, get_server

project_router = APIRouter(
    prefix="/projects/{project_id}",
    tags=["_project"],
)


async def get_project_from_id(project_id: str) -> Project:
    try:
        return get_panoptic().get_project(int(project_id))
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")


@project_router.get('/project_state')
async def get_project_state(project: Project = Depends(get_project_from_id)):
    return project.get_state()


@project_router.get("/db_state")
async def get_db_state_route(project: Project = Depends(get_project_from_id)):
    now = time()
    instances = await project.db.get_instances()
    get_properties = project.db.get_properties(computed=True)
    get_tags = project.db.get_tags()
    get_image_values = project.db.get_image_property_values()
    get_instance_values = project.db.get_instance_property_values()
    get_property_groups = project.db.get_property_groups()

    get_all = asyncio.gather(get_properties, get_tags, get_image_values, get_instance_values, get_property_groups)
    properties, tags, img_values, instance_values, property_groups = await get_all

    state = DbCommit(instances=instances, properties=properties, tags=tags, image_values=img_values,
                     instance_values=instance_values, property_groups=property_groups)
    print(time() - now)
    return ORJSONResponse(state)


@project_router.get('/db_state_stream')
async def stream_db_state(project: Project = Depends(get_project_from_id)):
    async def load_routine():
        state = LoadState()
        chunk_size = 10000

        state.max_instance_value = await project.db.get_instance_values_count()
        state.max_image_value = await project.db.get_image_values_count()
        state.max_instance = await project.db.get_instances_count()

        while not state.finished():
            if not state.finished_property:
                props = await project.db.get_properties(computed=True)
                chunk = DbCommit(properties=props)
                state.finished_property = True
                yield orjson.dumps(asdict(LoadResult(chunk=chunk, state=state)))
            if not state.finished_property_groups:
                groups = await project.db.get_property_groups()
                chunk = DbCommit(property_groups=groups)
                state.finished_property_groups = True
                yield orjson.dumps(asdict(LoadResult(chunk=chunk, state=state)))
            if not state.finished_tags:
                tags = await project.db.get_tags()
                chunk = DbCommit(tags=tags)
                state.finished_tags = True
                yield orjson.dumps(asdict(LoadResult(chunk=chunk, state=state)))

            if not state.finished_instance:
                instances, end = await project.db.stream_instances(state.counter_instance, chunk_size)
                chunk = DbCommit(instances=instances)
                state.counter_instance += len(instances)
                state.finished_instance = end
                yield orjson.dumps(asdict(LoadResult(chunk=chunk, state=state)))
            elif not state.finished_instance_values:
                values, end = await project.db.stream_instance_property_values(state.counter_instance_value, chunk_size)
                chunk = DbCommit(instance_values=values)
                state.counter_instance_value += len(values)
                state.finished_instance_values = end
                yield orjson.dumps(asdict(LoadResult(chunk=chunk, state=state)))
            elif not state.finished_image_values:
                values, end = await project.db.stream_image_property_values(state.counter_image_value, chunk_size)
                chunk = DbCommit(image_values=values)
                state.counter_image_value += len(values)
                state.finished_image_values = end
                yield orjson.dumps(asdict(LoadResult(chunk=chunk, state=state)))

    return StreamingResponse(load_routine(), media_type="application/json")


@project_router.get("/property")
async def get_properties_route(project: Project = Depends(get_project_from_id)) -> list[Property]:
    return await project.db.get_properties(computed=True)


@project_router.post('/import/upload')
async def upload_file_route(file: UploadFile, project: Project = Depends(get_project_from_id)):
    res = await project.importer.upload_csv(file.file)
    return res


@project_router.post('/import/parse')
async def import_parse_file_route(req: ImportPayload, project: Project = Depends(get_project_from_id)):
    missing = await project.importer.parse_file(req.exclude, properties=req.properties, relative=req.relative,
                                                fusion=req.fusion)
    return missing


@project_router.post('/import/confirm')
async def import_confirm_route(project: Project = Depends(get_project_from_id)):
    res = await project.importer.confirm_import()
    return ORJSONResponse(res)


@project_router.post('/export')
async def export_properties_route(req: ExportPropertiesPayload, project: Project = Depends(get_project_from_id)):
    await project.export_data(req.name, req.images, req.properties, req.export_images, req.key)
    return True

@project_router.get("/history")
async def get_history_route(project: Project = Depends(get_project_from_id)):
    undo, redo = project.db.undo_queue.stats()
    return CommitHistory(undo=undo, redo=redo)


@project_router.get("/tags", response_class=ORJSONResponse)
async def get_tags_route(prop: Optional[int] = None, project: Project = Depends(get_project_from_id)):
    tags = await project.db.get_tags(prop)
    return ORJSONResponse(tags)


@project_router.post("/tags/merge")
async def post_tags_merge_route(req: TagMergePayload, project: Project = Depends(get_project_from_id)):
    return await project.db.merge_tags(req.tag_ids)


@project_router.get("/folders")
async def get_folders_route(project: Project = Depends(get_project_from_id)):
    res = await project.db.get_folders()
    return res


@project_router.get('/update')
async def get_update_route(project: Project = Depends(get_project_from_id)):
    update = Update()
    if project.ui.commits:
        update.commits = [*project.ui.commits]
    if project.ui.plugins:
        update.plugins = [*project.ui.plugins]
    if project.ui.actions:
        update.actions = [*project.ui.actions]
    project.ui.clear()

    update.status = project.get_status_update()

    return update


class PathRequest(BaseModel):
    path: str


class IdRequest(BaseModel):
    id: int


@project_router.post("/folders")
async def add_folder_route(path: PathRequest, project: Project = Depends(get_project_from_id)):
    await project.import_folder(path.path)
    return await project.db.get_folders()


@project_router.post("/reimport_folder")
async def reimport_folder_route(req: IdRequest, project: Project = Depends(get_project_from_id)):
    try:
        folder = await project.db.get_folder(req.id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f'Folder id does not exist [{req.id}]')
    await project.import_folder(folder.path)
    return await project.db.get_folders()


@project_router.delete('/folder')
async def delete_folder(folder_id: int, project: Project = Depends(get_project_from_id)):
    res = await project.delete_folder(folder_id)
    return res


@project_router.post('/action_execute')
async def execute_action_route(req: ExecuteActionPayload, project: Project = Depends(get_project_from_id)):
    res = await project.action.call(req.function, req.context)
    if is_dataclass(res):
        return ORJSONResponse(res)
    return res


@project_router.get('/actions')
async def get_action_descriptions(project: Project = Depends(get_project_from_id)):
    actions = project.action.actions.values()
    return {a.id: a.description for a in actions}


@project_router.get('/plugins_info')
async def get_plugins(project: Project = Depends(get_project_from_id)):
    res = await project.plugins_info()
    return res


@project_router.get('/ui_data/{key:path}')
async def get_ui_data(key: str, request: Request, project: Project = Depends(get_project_from_id)):
    connection_id = request.query_params.get('connection_id')
    user = get_server().client_states[connection_id].user
    user_id = 0
    if user:
        user_id = user.id

    key = f"user:{user_id}.{key}"
    if key:
        return await project.db.get_ui_data(key=key)
    return await project.db.get_all_ui_data()


@project_router.post('/ui_data')
async def set_ui_data(req: UIDataPayload, request: Request, project: Project = Depends(get_project_from_id)):
    connection_id = request.query_params.get('connection_id')
    user = get_server().client_states[connection_id].user
    user_id = 0
    if user:
        user_id = user.id
    if not req.key:
        raise HTTPException(status_code=400, detail='set_ui_data UIDataPayload: no key given')
    key = f"user:{user_id}.{req.key}"
    return await project.db.set_ui_data(key, req.data)


@project_router.post('/plugin_params')
async def post_plugin_params_route(req: PluginParamsPayload, project: Project = Depends(get_project_from_id)):
    await project.set_plugin_params(req.plugin, req.params)
    return await get_plugins(project)


@project_router.get('/vectors_info')
async def get_vectors_info(project: Project = Depends(get_project_from_id)):
    vectors_description = await project.db.get_vectors_info()
    return vectors_description


@project_router.get('/vector_types')
async def get_vector_types(project: Project = Depends(get_project_from_id)):
    types = await project.db.get_vector_types()
    return types


@project_router.get('/vector_stats')
async def get_vector_stats(project: Project = Depends(get_project_from_id)):
    stats = await project.db.get_vector_stats()
    return stats


@project_router.post('/delete_vector_type')
async def post_delete_vector_type(req: DeleteVectorTypePayload, project: Project = Depends(get_project_from_id)):
    await project.delete_vector_type(req.id)


@project_router.post('/default_vectors')
async def set_default_vectors(vector_description: VectorDescription, project: Project = Depends(get_project_from_id)):
    await project.db.set_default_vectors(vector_description)
    return await get_vectors_info(project)


@project_router.post('/undo')
async def undo_route(project: Project = Depends(get_project_from_id)):
    res = await project.db.undo_queue.undo()
    return ORJSONResponse(res)


@project_router.post('/redo')
async def redo_route(project: Project = Depends(get_project_from_id)):
    res = await project.db.undo_queue.redo()
    return ORJSONResponse(res)


@project_router.post('/commit')
async def commit_route(commit: DbCommit, project: Project = Depends(get_project_from_id)):
    if commit.undo:
        await project.db.undo_queue.do(commit)
    else:
        await project.db.apply_commit(commit)
    return ORJSONResponse(commit)


@project_router.get('/image/raw/{sha1:path}')
async def get_image_raw_route(sha1: str, project: Project = Depends(get_project_from_id)):
    order = raw_order
    for getter in order:
        res = await getter(project, sha1)
        if res:
            return res


@project_router.get('/image/large/{sha1:path}')
async def get_image_large_route(sha1: str, project: Project = Depends(get_project_from_id)):
    order = large_order
    for getter in order:
        res = await getter(project, sha1)
        if res:
            return res


@project_router.get('/image/medium/{sha1:path}')
async def get_image_medium_route(sha1: str, project: Project = Depends(get_project_from_id)):
    order = medium_order
    for getter in order:
        res = await getter(project, sha1)
        if res:
            return res


@project_router.get('/image/small/{sha1:path}')
async def get_image_small_route(sha1: str, project: Project = Depends(get_project_from_id)):
    order = small_order
    for getter in order:
        res = await getter(project, sha1)
        if res:
            return res


@project_router.get('/settings')
async def get_settings_route(project: Project = Depends(get_project_from_id)):
    return project.settings


@project_router.post('/settings')
async def post_settings_route(settings: ProjectSettings, project: Project = Depends(get_project_from_id)):
    await project.update_settings(settings)
    return project.settings


@project_router.post('/delete_empty_clones')
async def post_delete_empty_clones(project: Project = Depends(get_project_from_id)):
    res = await project.delete_empty_instance_clones()
    return res


class EndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        update = record.getMessage().find("/update") > -1
        state = record.getMessage().find("/import_status") > -1
        small_img = record.getMessage().find("/small/images/") > -1
        img = record.getMessage().find("/image/") > -1
        return not (state or small_img or img or update)


# Filter out /endpoint
logging.getLogger("uvicorn.access").addFilter(EndpointFilter())
