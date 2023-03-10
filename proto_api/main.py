import os
from typing import Optional

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request
from starlette.responses import Response

from core import execute_query, create_property, add_property_to_image, add_image, get_images, create_tag, \
    _get_tag_by_id, _get_tag_ancestors
from models import Property, Images
from payloads import ImagePayload, PropertyPayload, AddImagePropertyPayload, AddTagPayload

app = FastAPI()

# TODO:
# ajouter une route static pour le mode serveur


# Route pour créer une property et l'insérer dans la table des properties
@app.post("/property")
async def create_property_route(payload: PropertyPayload):
    property_id = await create_property(payload.name, payload.type)
    return Property(id=property_id, name=payload.name, type=payload.type.value)


# Route pour supprimer une property d'une image dans la table de jointure entre image et property
@app.delete("/property")
async def delete_property(property_id: str, sha1: str):
    await execute_query('DELETE FROM images_properties WHERE property_id = ? AND sha1 = ?', (property_id, sha1))
    return {"property_id": property_id, "image_id": sha1}


# Route pour ajouter une image
@app.post("/images")
async def add_image_route(image: ImagePayload):
    await add_image(image.file_path)

    return {"message": "Image ajoutée avec succès"}


# Route pour récupérer la liste de toutes les images
@app.get("/images")
async def get_images_route():
    images = await get_images()
    return Images(images)


@app.get('/images/{file_path:path}')
def get_image(file_path: str):

    with open(file_path, 'rb') as f:
        data = f.read()

    ext = file_path.split('.')[-1]

    # # media_type here sets the media type of the actual response sent to the client.
    return Response(content=data, media_type="image/" + ext)


# Route pour ajouter une property à une image dans la table de jointure entre image et property
# On retourne le payload pour pouvoir valider l'update côté front
@app.post("/image_property")
async def add_image_property(payload: AddImagePropertyPayload):
    await add_property_to_image(payload.property_id, payload.sha1, payload.value)
    return payload


@app.post("/add_tag")
async def add_tag(payload: AddTagPayload):
    if not payload.parent_id:
        payload.parent_id = 0
    return await create_tag(payload.property_id, payload.value, payload.parent_id)

@app.get("/test")
async def test_route():
    tag = await _get_tag_by_id("5")
    return await _get_tag_ancestors(tag)