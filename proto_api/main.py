import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from db import execute_query, create_data_model, add_data_to_image, add_image, get_images
from models import DataModel, Images
from payloads import ImagePayload, DataPayload, AddImageDataPayload

app = FastAPI()
app.mount("/static", StaticFiles(directory=os.getenv('PANOPTIC_ROOT', os.path.expanduser('~'))), name="static")


# Route pour créer une définition metadata et l'insérer dans la table des metadata
@app.post("/data")
async def create_data_route(payload: DataPayload):
    data_id = await create_data_model(payload.name, payload.type)
    return DataModel(id=data_id, name=payload.name, type=payload.type.value)


# Route pour ajouter une data à une image dans la table de jointure entre image et data
# On retourne le payload pour pouvoir valider l'update côté front
@app.post("/image_data")
async def add_image_data(payload: AddImageDataPayload):
    await add_data_to_image(payload.data_id, payload.sha1, payload.value)
    return payload


# Route pour supprimer une data d'une image dans la table de jointure entre image et data
@app.delete("/data")
async def delete_data(data_id: str, sha1: str):
    await execute_query('DELETE FROM images_data WHERE data_id = ? AND sha1 = ?', (data_id, sha1))
    return {"metadata_id": data_id, "image_id": sha1}


# # Route pour modifier une metadata d'une image dans la table de jointure entre image et metadata
# @app.put("/image_metadata")
# async def update_image_metadata(metadata_id: str, metadata_value: str, image_id: str):
#     execute_query('UPDATE image_metadata SET metadata_value = ? WHERE metadata_id = ? AND image_id = ?', (metadata_value, metadata_id, image_id))
#     return {"metadata_id": metadata_id, "metadata_value": metadata_value, "image_id": image_id}


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