import logging
import os
from sys import platform
from typing import Optional

import aiofiles as aiofiles
import pandas as pd
from fastapi import FastAPI, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse, StreamingResponse
from pydantic import BaseModel
from starlette.responses import Response
from starlette.staticfiles import StaticFiles

from panoptic import core
from panoptic.compute.similarity import get_similar_images_from_text, reload_tree
from panoptic.core import create_property, create_tag, \
    update_tag, get_tags, get_properties, delete_property, update_property, delete_tag, delete_tag_parent, add_folder, \
    db_utils, make_clusters, get_similar_images, read_properties_file, get_full_images, set_property_values, \
    tag_add_parent, export_properties
from panoptic.core import db
from panoptic.models import Property, Tag, Properties, PropertyPayload, \
    SetPropertyValuePayload, AddTagPayload, DeleteImagePropertyPayload, \
    UpdateTagPayload, UpdatePropertyPayload, Tab, MakeClusterPayload, GetSimilarImagesPayload, \
    ChangeProjectPayload, Clusters, GetSimilarImagesFromTextPayload, AddTagParentPayload, ExportPropertiesPayload

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# # TODO:
# ajouter une route static pour le mode serveur

@app.on_event("startup")
async def startup_event():
    await db_utils.init()


# Route pour créer une property et l'insérer dans la table des properties
@app.post("/property")
async def create_property_route(payload: PropertyPayload) -> Property:
    return await create_property(payload.name, payload.type, payload.mode)


@app.get("/property")
async def get_properties_route() -> Properties:
    return await get_properties()


@app.patch("/property")
async def update_property_route(payload: UpdatePropertyPayload) -> Property:
    return await update_property(payload)


@app.post('/property/file')
async def properties_by_file(file: UploadFile):
    data = pd.read_csv(file.file, sep=";")
    return await read_properties_file(data)


@app.post('/export')
async def export_properties_route(payload: ExportPropertiesPayload) -> StreamingResponse:
    stream = await export_properties(payload.images, payload.properties)
    response = StreamingResponse(iter([stream.getvalue()]),
                                 media_type="text/csv"
                                 )
    response.headers["Content-Disposition"] = "attachment; filename=export.csv"
    return response

@app.delete('/property/{property_id}')
async def delete_property_route(property_id: str):
    await delete_property(property_id)
    return await get_properties()


# Route pour récupérer la liste de toutes les images
@app.get("/images", response_class=ORJSONResponse)
async def get_images_route():
    images = await get_full_images()
    return ORJSONResponse(images)


@app.get('/images/{file_path:path}')
async def get_image(file_path: str):
    if platform == "linux" or platform == "linux2" or platform == "darwin":
        if not file_path.startswith('/'):
            file_path = '/' + file_path
    # print(file_path)
    async with aiofiles.open(file_path, 'rb') as f:
        data = await f.read()

    ext = file_path.split('.')[-1]

    # # media_type here sets the media type of the actual response sent to the client.
    return Response(content=data, media_type="image/" + ext)


# Route pour ajouter une property à une image dans la table de jointure entre image et property
# On retourne le payload pour pouvoir valider l'update côté front
@app.post("/image_property")
async def add_image_property(payload: SetPropertyValuePayload):
    updated, value = await set_property_values(property_id=payload.property_id, image_ids=payload.image_ids,
                                               sha1s=payload.sha1s, value=payload.value)
    return {'updated_ids': updated, 'value': value}


# Route pour supprimer une property d'une image dans la table de jointure entre image et property
@app.delete("/image_property")
async def delete_property_value_route(payload: DeleteImagePropertyPayload) -> DeleteImagePropertyPayload:
    await db.delete_property_value(payload.property_id, image_ids=[payload.image_id])
    return payload


@app.post("/tags")
async def add_tag(payload: AddTagPayload) -> Tag:
    if not payload.parent_id:
        payload.parent_id = 0
    return await create_tag(payload.property_id, payload.value, payload.parent_id, payload.color)


@app.post("/tag/parent")
async def add_tag_parent(payload: AddTagParentPayload) -> Tag:
    return await tag_add_parent(payload.tag_id, payload.parent_id)


@app.get("/tags", response_class=ORJSONResponse)
async def get_tags_route(property: Optional[str] = None):
    tags = await get_tags(property)
    return ORJSONResponse(tags)


@app.patch("/tags")
async def update_tag_route(payload: UpdateTagPayload) -> Tag:
    return await update_tag(payload)


@app.delete("/tags")
async def delete_tag_route(tag_id: int) -> list[int]:
    return await delete_tag(tag_id)


@app.delete("/tags/parent")
async def delete_tag_parent_route(tag_id: int, parent_id: int):
    res = await delete_tag_parent(tag_id, parent_id)
    return res


@app.get("/folders")
async def get_folders_route():
    res = await db.get_folders()
    return res


@app.get('/import_status')
async def get_import_status_route():
    image_import = core.importer
    new_image = image_import.get_new_images()

    update = []
    if new_image:
        update = await get_full_images(new_image)

    res = {
        'to_import': image_import.total_import,
        'imported': image_import.current_import,
        'computed': image_import.current_computed,
        'new_images': update,
        'done': image_import.import_done()
    }
    return res


class PathRequest(BaseModel):
    path: str


@app.post("/folders")
async def add_folder_route(path: PathRequest):
    # TODO: safe guards do avoid adding folder inside already imported folder. Also inverse direction
    nb_images = await add_folder(path.path)
    return await get_folders_route()


@app.get("/tabs")
async def get_tabs_route():
    return await db.get_tabs()


@app.post("/tab")
async def add_tab_route(tab: Tab):
    return await db.add_tab(tab.name, tab.data)


@app.patch("/tab")
async def update_tab_route(tab: Tab):
    return await db.update_tab(tab)


@app.delete("/tab")
async def delete_tab_route(tab_id: int):
    return await db.delete_tab(tab_id)


@app.post("/clusters")
async def make_clusters_route(payload: MakeClusterPayload) -> Clusters:
    return await make_clusters(payload.nb_groups, payload.image_list)


@app.post("/similar/image")
async def get_similar_images_route(payload: GetSimilarImagesPayload) -> list:
    return await get_similar_images(payload.sha1_list)


@app.post("/similar/text")
async def get_similar_images_from_text_route(payload: GetSimilarImagesFromTextPayload) -> list:
    return await get_similar_images_from_text(payload.input_text)


# @app.post("/pca")
# async def start_pca_route():
#     return await compute_all_pca(force=True)


@app.post("/project")
async def change_project_route(payload: ChangeProjectPayload):
    os.environ['PANOPTIC_DATA'] = payload.project
    await db_utils.init()
    reload_tree()
    return f"changed project to {payload.project}"


@app.get('/small/images/{file_path:path}')
async def get_image(file_path: str):
    path = os.path.join(os.environ['PANOPTIC_DATA'], 'mini', file_path)
    async with aiofiles.open(path, 'rb') as f:
        data = await f.read()

    ext = path.split('.')[-1]

    # # media_type here sets the media type of the actual response sent to the client.
    return Response(content=data, media_type="image/" + ext)


# app.mount("/small/images/", StaticFiles(directory=os.path.join('PANOPTIC_DATA', 'mini')), name="static")
app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "html"), html=True), name="static")


class EndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.getMessage().find("/import_status") == -1


# Filter out /endpoint
logging.getLogger("uvicorn.access").addFilter(EndpointFilter())
