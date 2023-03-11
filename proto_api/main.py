import os
from typing import Optional

from fastapi import FastAPI, Body
from starlette.responses import Response

from core import create_property, add_property_to_image, add_image, get_images, create_tag, delete_image_property, \
    update_tag, get_tags
from models import Property, Images, Tag, Image, Tags
from payloads import ImagePayload, PropertyPayload, AddImagePropertyPayload, AddTagPayload, DeleteImagePropertyPayload, \
    UpdateTagPayload

app = FastAPI()

# TODO:
# ajouter une route static pour le mode serveur


# Route pour créer une property et l'insérer dans la table des properties
@app.post("/property")
async def create_property_route(payload: PropertyPayload) -> Property:
    return await create_property(payload.name, payload.type)


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
def get_image(file_path: str):

    with open(file_path, 'rb') as f:
        data = f.read()

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


@app.patch("/image_property")
async def update_image_property(new_value: str = Body(..., embed=True)) -> str:
    pass


@app.patch("/property")
async def update_property(payload: str):
    pass

# TODO: add update image property
# TODO: add update property
# TODO: add add folder