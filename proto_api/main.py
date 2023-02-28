import uuid
from typing import Optional

from fastapi import FastAPI
import hashlib

from db import execute_query, create_metadata


app = FastAPI()


# Route pour créer une définition metadata et l'insérer dans la table des metadata
@app.post("/metadata")
async def create_metadata_route(nom: str, type: str, hierarchical: bool):
    metadata_id = str(uuid.uuid4())
    execute_query('INSERT INTO metadata (id, nom, type, hierarchical) VALUES (?, ?, ?, ?)', (metadata_id, nom, type, hierarchical))
    return {"id": metadata_id, "nom": nom, "type": type, "hierarchical": hierarchical}


# Route pour ajouter une metadata à une image dans la table de jointure entre image et metadata
@app.post("/image_metadata")
async def add_image_metadata(metadata_id: str, metadata_value: str, image_id: str):
    execute_query('INSERT INTO image_metadata (metadata_id, metadata_value, image_id) VALUES (?, ?, ?)', (metadata_id, metadata_value, image_id))
    return {"metadata_id": metadata_id, "metadata_value": metadata_value, "image_id": image_id}


# Route pour supprimer une metadata d'une image dans la table de jointure entre image et metadata
@app.delete("/image_metadata")
async def delete_image_metadata(metadata_id: str, image_id: str):
    execute_query('DELETE FROM image_metadata WHERE metadata_id = ? AND image_id = ?', (metadata_id, image_id))
    return {"metadata_id": metadata_id, "image_id": image_id}


# Route pour modifier une metadata d'une image dans la table de jointure entre image et metadata
@app.put("/image_metadata")
async def update_image_metadata(metadata_id: str, metadata_value: str, image_id: str):
    execute_query('UPDATE image_metadata SET metadata_value = ? WHERE metadata_id = ? AND image_id = ?', (metadata_value, metadata_id, image_id))
    return {"metadata_id": metadata_id, "metadata_value": metadata_value, "image_id": image_id}


# Route pour ajouter une image
@app.post("/images")
async def add_image(file_path: str):
    with open(file_path, "rb") as image_file:
        # Calcul du sha1 de l'image
        sha1_hash = hashlib.sha1(image_file.read()).hexdigest()

        # Vérification de l'existence de la metadata sha1
        query = """
            SELECT id FROM metadata WHERE id = 'sha1'
        """
        result = execute_query(query)
        if not result:
            # Si la metadata sha1 n'existe pas, on la crée
            create_metadata({"id": "sha1", "nom": "SHA1 hash", "type": "string", "hierarchical": False})

        # Ajout de l'image à la table images
        query = """
            INSERT INTO images (id, file_path)
            VALUES (?, ?)
        """
        execute_query(query, (sha1_hash, file_path))

        # Ajout de la metadata sha1 à l'image
        query = """
            INSERT INTO images_metadata (metadata_id, metadata_value, image_id)
            VALUES (?, ?, ?)
        """
        execute_query(query, ("sha1", sha1_hash, sha1_hash))

    return {"message": "Image ajoutée avec succès"}


# Route pour récupérer la liste de toutes les images avec pagination
@app.get("/images")
async def get_images(skip: Optional[int] = 0, limit: Optional[int] = 10):
    query = """
        SELECT * FROM images
        ORDER BY id DESC
        LIMIT ? OFFSET ?
    """
    result = execute_query(query, (limit, skip))
    images = []
    for row in result:
        image = {"id": row[0], "file_path": row[1]}
        images.append(image)
    return {"images": images}


# Route pour récupérer les metadata d'une image donnée
@app.get("/images/{image_id}/metadata")
async def get_image_metadata(image_id: str):
    query = """
        SELECT metadata.id, metadata.nom, metadata.type, metadata.hierarchical, images_metadata.metadata_value
        FROM metadata
        INNER JOIN images_metadata ON metadata.id = images_metadata.metadata_id
        WHERE images_metadata.image_id = ?
    """
    result = execute_query(query, (image_id,))
    metadata = []
    for row in result:
        metadata_item = {"metadata_id": row[0], "nom": row[1], "type": row[2], "hierarchical": row[3], "metadata_value": row[4]}
        metadata.append(metadata_item)
    return {"metadata": metadata}