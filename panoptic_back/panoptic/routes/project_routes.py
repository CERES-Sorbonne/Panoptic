import asyncio
import logging
from dataclasses import asdict
from sys import platform
from time import time
from typing import Optional

from fastapi import APIRouter, UploadFile
from fastapi.responses import ORJSONResponse
import orjson
from pydantic import BaseModel
from starlette.responses import FileResponse, StreamingResponse

from panoptic.core.project.project import Project
from panoptic.models import Property, VectorDescription, ExecuteActionPayload, \
    ExportPropertiesPayload, UIDataPayload, PluginParamsPayload, ImportPayload, DbCommit, CommitHistory, Update, \
    ProjectSettings, TagMergePayload, LoadState
from panoptic.models.results import LoadResult
from panoptic.routes.image_utils import medium_order, large_order, small_order, raw_order

project_router = APIRouter()

project: Project | None = None


def set_project(p: Project | None):
    global project
    project = p


@project_router.get("/db_state")
async def get_db_state_route():
    now = time()
    instances = await project.db.get_instances()
    get_properties = project.db.get_properties(computed=True)
    get_tags = project.db.get_tags()
    # get_values = project.db.get_property_values(instances, property_ids= no_computed=True)
    get_image_values = project.db.get_image_property_values()
    get_instance_values = project.db.get_instance_property_values()
    get_property_groups = project.db.get_property_groups()

    get_all = asyncio.gather(get_properties, get_tags, get_image_values, get_instance_values, get_property_groups)
    properties, tags, img_values, instance_values, property_groups = await get_all
    # computed_values = project.db.get_computed_values(instances)
    # instance_values.extend(computed_values)

    state = DbCommit(instances=instances, properties=properties, tags=tags, image_values=img_values,
                     instance_values=instance_values, property_groups=property_groups)
    print(time() - now)
    return ORJSONResponse(state)
    # return state


@project_router.get('/db_state_stream')
async def stream_db_state():
    async def load_routine():
        state = LoadState()
        chunk_size = 10000

        state.max_instance_value = await project.db.get_raw_db().get_instance_values_count()
        state.max_image_value = await project.db.get_raw_db().get_image_values_count()
        state.max_instance = await project.db.get_raw_db().get_instances_count()

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
async def get_properties_route() -> list[Property]:
    return await project.db.get_properties(computed=True)


@project_router.post('/import/upload')
async def upload_file_route(file: UploadFile):
    res = await project.importer.upload_csv(file.file)
    return res
    # return await project.importer.analyse_file()


# @project_router.post('/import/confirm')
# async def import_parse_route(req: ImportPayload):
#     await project.importer.parse_file(req.exclude, properties=req.properties, relative=req.relative, fusion=req.fusion)
#     res = await project.importer.confirm_import()
#     return ORJSONResponse(res)


@project_router.post('/import/parse')
async def import_parse_file_route(req: ImportPayload):
    missing = await project.importer.parse_file(req.exclude, properties=req.properties, relative=req.relative,
                                                fusion=req.fusion)
    return missing


@project_router.post('/import/confirm')
async def import_confirm_route():
    res = await project.importer.confirm_import()
    return ORJSONResponse(res)


@project_router.post('/export')
async def export_properties_route(req: ExportPropertiesPayload):
    await project.export_data(req.name, req.images, req.properties, req.export_images, req.key)
    return True


@project_router.get('/images/{file_path:path}')
async def get_image(file_path: str):
    if platform == "linux" or platform == "linux2" or platform == "darwin":
        if not file_path.startswith('/'):
            file_path = '/' + file_path
    return FileResponse(path=file_path)


@project_router.get("/history")
async def get_history_route():
    undo, redo = project.db.undo_queue.stats()
    return CommitHistory(undo=undo, redo=redo)


@project_router.get("/tags", response_class=ORJSONResponse)
async def get_tags_route(prop: Optional[int] = None):
    tags = await project.db.get_tags(prop)
    return ORJSONResponse(tags)


@project_router.post("/tags/merge")
async def post_tags_merge_route(req: TagMergePayload):
    return await project.db.merge_tags(req.tag_ids)


@project_router.get("/folders")
async def get_folders_route():
    res = await project.db.get_folders()
    return res


@project_router.get('/update')
async def get_update_route():
    if not project:
        return None
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
async def add_folder_route(path: PathRequest):
    # TODO: safe guards do avoid adding folder inside already imported folder. Also inverse direction
    nb_images = await project.import_folder(path.path)
    return await get_folders_route()


@project_router.post("/reimport_folder")
async def reimport_folder_route(req: IdRequest):
    folder = await project.db.get_folder(req.id)
    if not folder:
        raise Exception(f'Folder id does not exist [{req.id}]')
    await project.import_folder(folder.path)
    return await get_folders_route()


@project_router.delete('/folder')
async def delete_folder(folder_id: int):
    res = await project.delete_folder(folder_id)
    return res


@project_router.post('/action_execute')
async def execute_action_route(req: ExecuteActionPayload):
    res = await project.action.call(req.function, req.context)
    return ORJSONResponse(res)


@project_router.get('/actions')
async def get_action_descriptions():
    actions = project.action.actions.values()
    return {a.id: a.description for a in actions}


@project_router.get('/plugins_info')
async def get_plugins():
    res = await project.plugins_info()
    return res


@project_router.get('/ui_data/{key:path}')
async def get_ui_data(key: str):
    if key:
        return await project.db.get_ui_data(key=key)
    return await project.db.get_all_ui_data()


@project_router.post('/ui_data')
async def set_ui_data(req: UIDataPayload):
    if not req.key:
        raise Exception('set_ui_data UIDataPayload: no key given')
    return await project.db.set_ui_data(req.key, req.data)


@project_router.post('/plugin_params')
async def post_plugin_params_route(req: PluginParamsPayload):
    await project.set_plugin_params(req.plugin, req.params)
    return await get_plugins()


@project_router.get('/vectors_info')
async def get_vectors_info():
    vectors_description = await project.db.get_vectors_info()
    return vectors_description


@project_router.post('/default_vectors')
async def set_default_vectors(vector_description: VectorDescription):
    await project.db.set_default_vectors(vector_description)
    return await get_vectors_info()


@project_router.post('/undo')
async def undo_route():
    res = await project.db.undo_queue.undo()
    return ORJSONResponse(res)


@project_router.post('/redo')
async def undo_route():
    res = await project.db.undo_queue.redo()
    return ORJSONResponse(res)


@project_router.post('/commit')
async def commit_route(commit: DbCommit):
    if commit.undo:
        await project.db.undo_queue.do(commit)
    else:
        await project.db.apply_commit(commit)
    return ORJSONResponse(commit)


@project_router.get('/image/raw/{sha1:path}')
async def get_image_raw_route(sha1: str):
    order = raw_order
    for getter in order:
        res = await getter(project, sha1)
        if res:
            return res


@project_router.get('/image/large/{sha1:path}')
async def get_image_large_route(sha1: str):
    order = large_order
    for getter in order:
        res = await getter(project, sha1)
        if res:
            return res


@project_router.get('/image/medium/{sha1:path}')
async def get_image_medium_route(sha1: str):
    order = medium_order
    for getter in order:
        res = await getter(project, sha1)
        if res:
            return res


@project_router.get('/image/small/{sha1:path}')
async def get_image_small_route(sha1: str):
    order = small_order
    for getter in order:
        res = await getter(project, sha1)
        if res:
            return res


@project_router.get('/settings')
async def get_settings_route():
    return project.settings


@project_router.post('/settings')
async def post_settings_route(settings: ProjectSettings):
    await project.update_settings(settings)
    return project.settings


class EndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        update = record.getMessage().find("/update") > -1
        state = record.getMessage().find("/import_status") > -1
        small_img = record.getMessage().find("/small/images/") > -1
        img = record.getMessage().find("/image/") > -1
        return not (state or small_img or img or update)


# Filter out /endpoint
logging.getLogger("uvicorn.access").addFilter(EndpointFilter())
