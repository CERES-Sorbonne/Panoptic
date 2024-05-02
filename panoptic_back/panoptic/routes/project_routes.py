import logging
import os
from sys import platform
from typing import Optional

from fastapi import APIRouter, UploadFile
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel
from starlette.responses import FileResponse

from panoptic.core.project.project import Project
from panoptic.models import Property, Tag, PropertyPayload, \
    SetPropertyValuePayload, AddTagPayload, \
    AddTagParentPayload, PropertyUpdate, \
    TagUpdate, VectorDescription, \
    ExecuteActionPayload, SetTagPropertyValuePayload, OptionsPayload, ExportPropertiesPayload, UIDataPayload, \
    PluginParamsPayload, ImportPayload

project_router = APIRouter()

project: Project | None = None


def set_project(p: Project | None):
    global project
    project = p


# Route pour créer une property et l'insérer dans la table des properties
@project_router.post("/property")
async def create_property_route(payload: PropertyPayload) -> Property:
    return await project.db.add_property(payload.name, payload.type, payload.mode)


@project_router.get("/property")
async def get_properties_route() -> list[Property]:
    return await project.db.get_properties()


@project_router.patch("/property")
async def update_property_route(payload: PropertyUpdate) -> Property:
    return await project.db.update_property(payload)


@project_router.post('/import/upload')
async def upload_file_route(file: UploadFile):
    key, props = await project.importer.upload_csv(file)
    return {"key": key, "properties": props}
    # return await project.importer.analyse_file()


@project_router.post('/import/confirm')
async def import_parse_route(req: ImportPayload):
    await project.importer.parse_file(req.exclude, properties=req.properties, relative=req.relative, fusion=req.fusion)
    await project.importer.confirm_import()


@project_router.post('/export')
async def export_properties_route(req: ExportPropertiesPayload):
    await project.export_data(req.name, req.images, req.properties, req.export_images)
    return True


@project_router.delete('/property/{property_id}')
async def delete_property_route(property_id: str):
    await project.db.delete_property(property_id)
    return await project.db.get_properties()


@project_router.get("/images", response_class=ORJSONResponse)
async def get_all_images_route():
    images = await project.db.get_instances_with_properties()
    return ORJSONResponse(images)


@project_router.get('/images/{file_path:path}')
async def get_image(file_path: str):
    if platform == "linux" or platform == "linux2" or platform == "darwin":
        if not file_path.startswith('/'):
            file_path = '/' + file_path
    return FileResponse(path=file_path)


# Route pour ajouter une property à une image dans la table de jointure entre image et property
# On retourne le payload pour pouvoir valider l'update côté front
@project_router.post("/image_property")
async def set_property_values_route(payload: SetPropertyValuePayload):
    values = await project.db.set_property_values(property_id=payload.property_id,
                                                  instance_ids=payload.instance_ids,
                                                  value=payload.value)
    return values


@project_router.post('/set_tag_property_value')
async def set_tag_property_value(payload: SetTagPropertyValuePayload):
    print(payload)
    values = await project.db.set_tag_property_value(property_id=payload.property_id, instance_ids=payload.instance_ids,
                                                     value=payload.value, mode=payload.mode)
    return values


@project_router.post("/tags")
async def add_tag(payload: AddTagPayload) -> Tag:
    if not payload.parent_id:
        payload.parent_id = 0
    return await project.db.add_tag(payload.property_id, payload.value, payload.parent_id, payload.color)


@project_router.post("/tag/parent")
async def add_tag_parent(payload: AddTagParentPayload) -> Tag:
    return await project.db.add_tag_parent(payload.tag_id, payload.parent_id)


@project_router.get("/tags", response_class=ORJSONResponse)
async def get_tags_route(prop: Optional[int] = None):
    tags = await project.db.get_tags(prop)
    return ORJSONResponse(tags)


@project_router.patch("/tags")
async def update_tag_route(payload: TagUpdate) -> Tag:
    return await project.db.update_tag(payload)


@project_router.delete("/tags")
async def delete_tag_route(tag_id: int):
    return await project.db.delete_tag(tag_id)


@project_router.delete("/tags/parent")
async def delete_tag_parent_route(tag_id: int, parent_id: int):
    res = await project.db.delete_tag_parent(tag_id, parent_id)
    return res


@project_router.get("/folders")
async def get_folders_route():
    res = await project.db.get_folders()
    return res


# TODO
@project_router.get('/import_status')
async def get_import_status_route():
    if not project:
        return None
    res = project.get_status_update()
    return res


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


#
# @project_router.get("/tabs")
# async def get_tabs_route():
#     return await project.ui.get_tabs()
#
#
# @project_router.post("/tab")
# async def add_tab_route(tab: Tab):
#     return await project.ui.add_tab(tab.data)
#
#
# @project_router.patch("/tab")
# async def update_tab_route(tab: Tab):
#     return await project.ui.update_tab(tab)
#
#
# @project_router.delete("/tab")
# async def delete_tab_route(tab_id: int):
#     return await project.ui.delete_tab(tab_id)


# @project_router.get('/actions_description')
# async def get_actions_description_route():
#     res = project.action.get_actions_description()
#     return res
#
#
# @project_router.post('/actions_functions')
# async def set_actions_update_route(actions_update: UpdateActionsPayload):
#     await project.set_action_updates(actions_update.updates)
#     return await get_actions_description_route()
#
#
# @project_router.post('/action_execute')
# async def execute_action_route(req: ExecuteActionPayload):
#     res = await project.action.actions[req.action].call(req.context, function=req.function)
#     return res

@project_router.post('/action_execute')
async def execute_action_route(req: ExecuteActionPayload):
    return await project.action.call(req.function, req.context)


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


#
# @project_router.post("/similar/text")
# async def get_similar_images_from_text_route(payload: GetSimilarImagesFromTextPayload) -> list:
#     return await get_similar_images_from_text(payload.input_text)


@project_router.get('/small/images/{file_path:path}')
async def get_image(file_path: str):
    path = os.path.join(project.base_path, 'mini', file_path)
    return FileResponse(path=path)


class EndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        state = record.getMessage().find("/import_status") > -1
        small_img = record.getMessage().find("/small/images/") > -1
        img = record.getMessage().find("/images/") > -1
        return not (state or small_img or img)


# Filter out /endpoint
logging.getLogger("uvicorn.access").addFilter(EndpointFilter())
