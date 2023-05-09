import asyncio
import logging
import tkinter
from sys import platform
from tkinter.filedialog import *
from typing import Optional

import multiprocessing as mp

import aiofiles as aiofiles
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import Response

from panoptic_api.core import create_property, add_property_to_image, add_image, get_images, create_tag, \
    delete_image_property, \
    update_tag, get_tags, get_properties, delete_property, update_property, delete_tag, delete_tag_parent, add_folder, \
    db_utils
from panoptic_api.models import Property, Images, Tag, Image, Tags, Properties, ImagePayload, PropertyPayload, \
    AddImagePropertyPayload, AddTagPayload, DeleteImagePropertyPayload, \
    UpdateTagPayload, UpdatePropertyPayload
from panoptic_api.core import db

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# TODO:
# ajouter une route static pour le mode serveur

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(db_utils.init())

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


# Route pour ajouter une image
@app.post("/images")
async def add_image_route(image: ImagePayload) -> Image:
    image = await add_image(image.file_path)
    return image


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
    return await create_tag(payload.property_id, payload.value, payload.parent_id)


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


@app.get("/params")
async def get_params():
    res = await db.get_parameters()
    return res


@app.post("/folders")
async def add_folder_route():
    queue = mp.Queue()
    process = mp.Process(target=ui_process, args=(queue,))
    process.start()
    process.join()
    folder = queue.get()
    if not folder:
        return
    nb_images = await add_folder(folder)
    return f"{nb_images} images were added to the library"


@app.post("/transform")
async def toggle_transform():
    pass


def ui_process(queue):
    root = tkinter.Tk()
    root.withdraw()
    folder_path = askdirectory(parent=root, title='Select a directory')
    root.destroy()
    queue.put(folder_path)
