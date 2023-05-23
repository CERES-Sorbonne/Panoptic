import os
from sys import platform
from typing import Optional

import aiofiles as aiofiles
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.responses import Response
from starlette.staticfiles import StaticFiles

from panoptic import core
from panoptic.core import create_property, add_property_to_image, get_images, create_tag, \
    delete_image_property, \
    update_tag, get_tags, get_properties, delete_property, update_property, delete_tag, delete_tag_parent, add_folder, \
    db_utils, make_clusters, get_similar_images
from panoptic.core import db
from panoptic.models import Property, Images, Tag, Tags, Properties, PropertyPayload, \
    AddImagePropertyPayload, AddTagPayload, DeleteImagePropertyPayload, \
    UpdateTagPayload, UpdatePropertyPayload, Tab, MakeClusterPayload

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
    return await create_property(payload.name, payload.type)


@app.get("/property")
async def get_properties_route() -> Properties:
    return await get_properties()


@app.patch("/property")
async def update_property_route(payload: UpdatePropertyPayload) -> Property:
    return await update_property(payload)


@app.delete('/property/{property_id}')
async def delete_property_route(property_id: str):
    await delete_property(property_id)
    return f"Property {property_id} correctly deleted"


# Route pour récupérer la liste de toutes les images
@app.get("/images")
async def get_images_route() -> Images:
    images = await get_images()
    return images


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
async def add_image_property(payload: AddImagePropertyPayload) -> AddImagePropertyPayload:
    await add_property_to_image(payload.property_id, payload.sha1, payload.value)
    return payload


# Route pour supprimer une property d'une image dans la table de jointure entre image et property
@app.delete("/image_property")
async def delete_property_route(payload: DeleteImagePropertyPayload) -> DeleteImagePropertyPayload:
    await delete_image_property(payload.property_id, payload.sha1)
    return payload


@app.post("/tags")
async def add_tag(payload: AddTagPayload) -> Tag:
    if not payload.parent_id:
        payload.parent_id = 0
    return await create_tag(payload.property_id, payload.value, payload.parent_id, payload.color)


@app.get("/tags")
async def get_tags_route(property: Optional[str] = None) -> Tags:
    return await get_tags(property)


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
    res = {'to_import': image_import.total_import, 'imported': image_import.current_import}
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
async def make_clusters_route(payload: MakeClusterPayload) -> list[list[str]]:
    return await make_clusters(payload.nb_groups, payload.image_list)


@app.get("/similar/{sha1}")
async def get_similar_images_route(sha1: str) -> list:
    return await get_similar_images(sha1)


app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "html"), html=True), name="static")
