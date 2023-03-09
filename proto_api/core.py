import hashlib
import json
import os
import sqlite3
from PIL import Image as pImage

from models import DataModel, DataType, JSON, Image

# Connexion à la base de données SQLite
conn = sqlite3.connect(os.getenv('PANOPTIC_DB'))


# Fonction utilitaire pour exécuter une requête SQL et commettre les modifications
async def execute_query(query: str, parameters: tuple = None):
    cursor = conn.cursor()
    if parameters:
        cursor.execute(query, parameters)
    else:
        cursor.execute(query)
    conn.commit()
    return cursor


# Fonction utilitaire pour créer une metadata
async def create_data_model(name: str, data_type: DataType):
    query = 'INSERT INTO datamodel (name, type) VALUES (?, ?)'
    cursor = await execute_query(query, (name, data_type.value))
    data_id = cursor.lastrowid
    return data_id


async def get_images():
    """
    Get all images from database
    :return:
    """
    # requête à optimiser en deux requêtes ? pcke là on récupère les paths de l'image pour chaque metadata,
    # ou alors solution c'est de considérer les paths comme une metadata
    query = """
        SELECT DISTINCT i.sha1, i.paths, d_m.id, d_m.name, d_m.type, i_d.value, i.url
        FROM images i
        LEFT JOIN images_data i_d ON i.sha1 = i_d.sha1
        LEFT JOIN datamodel d_m ON i_d.data_id = d_m.id
        """
    cursor = await execute_query(query)
    rows = cursor.fetchall()
    result = {}
    for row in rows:
        sha1, paths, data_id, name, data_type, value, url = row
        if sha1 not in result:
            result[sha1] = {'data': {}, 'paths': json.loads(paths), 'url': url}
        if data_id:
            result[sha1]['data'][data_id] = {'id': data_id, 'name': name, 'type': data_type,
                                             'value': json.loads(value)}
    return result


async def add_data_to_image(data_id: int, sha1: str, value: JSON):
    query = """
            INSERT INTO images_data (data_id, sha1, value)
            VALUES (?, ?, ?)
    """
    await execute_query(query, (data_id, sha1, json.dumps(value)))
    return value


async def add_image(file_path):
    image = pImage.open(file_path)
    name = file_path.split(os.sep)[-1]
    extension = name.split('.')[-1]
    width, height = image.size
    sha1_hash = hashlib.sha1(image.tobytes()).hexdigest()
    # TODO: gérer l'url statique quand on sera en mode serveur
    url = os.path.join('/static/' + file_path.split(os.getenv('PANOPTIC_ROOT'))[1].replace('\\', '/'))
    url = f"/images/{file_path}"
    # Vérification si sha1_hash existe déjà dans la table images
    query = """
        SELECT paths
        FROM images
        WHERE sha1 = ?
    """
    cursor = await execute_query(query, (sha1_hash,))
    paths = cursor.fetchone()
    # Si sha1_hash existe déjà, on ajoute file_path à la liste de paths
    if paths:
        paths = json.loads(paths[0])
        if file_path not in paths:
            paths.append(file_path)

        # Mise à jour de la liste de paths
        query = """
            UPDATE images
            SET paths = ?
            WHERE sha1 = ?
        """
        await execute_query(query, (json.dumps(paths), sha1_hash))

    # Si sha1_hash n'existe pas, on l'ajoute avec la liste de paths contenant file_path
    else:
        query = """
            INSERT INTO images (sha1, height, width, name, extension, paths, url)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        await execute_query(query, (sha1_hash, height, width, name, extension, json.dumps([file_path]), url))
