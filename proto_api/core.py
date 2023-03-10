import hashlib
import json
import os
import sqlite3
from PIL import Image as pImage
from fastapi import HTTPException

from models import Property, PropertyType, JSON, Image, Tag

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
async def create_property(name: str, property_type: PropertyType):
    query = 'INSERT INTO datamodel (name, type) VALUES (?, ?)'
    cursor = await execute_query(query, (name, property_type.value))
    property_id = cursor.lastrowid
    return property_id


async def get_images():
    """
    Get all images from database
    :return:
    """
    # requête à optimiser en deux requêtes ? pcke là on récupère les paths de l'image pour chaque property,
    # ou alors solution c'est de considérer les paths comme une property
    query = """
        SELECT DISTINCT i.sha1, i.paths, p.id, p.name, p.type, i_d.value, i.url
        FROM images i
        LEFT JOIN images_properties i_d ON i.sha1 = i_d.sha1
        LEFT JOIN properties p ON i_d.property_id = p.id
        """
    cursor = await execute_query(query)
    rows = cursor.fetchall()
    result = {}
    for row in rows:
        sha1, paths, property_id, name, property_type, value, url = row
        if sha1 not in result:
            result[sha1] = {'properties': {}, 'paths': json.loads(paths), 'url': url}
        if property_id:
            result[sha1]['properties'][property_id] = {'id': property_id, 'name': name, 'type': property_type,
                                                       'value': json.loads(value)}
    return result


async def add_property_to_image(property_id: int, sha1: str, value: JSON):
    query = """
            INSERT INTO images_properties (property_id, sha1, value)
            VALUES (?, ?, ?)
    """
    await execute_query(query, (property_id, sha1, json.dumps(value)))
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


async def create_tag(property_id, value, parent_id) -> Tag:
    existing_tag = await _get_tag(property_id, value)
    if existing_tag is not None:
        parent = await _get_tag_by_id(parent_id)
        ancestors = await _get_tag_ancestors(parent)
        if existing_tag.id in ancestors:
            raise HTTPException(status_code=400, detail="Adding a tag that is an ancestor of himself")
        parents = list({*existing_tag.parents, parent_id})
        query = "UPDATE tags SET parents = ? WHERE property_id = ? AND value = ?"
        await execute_query(query, (json.dumps(parents), property_id, value))
        tag_id = existing_tag.id
    else:
        parents = [parent_id]
        query = "INSERT INTO tags (property_id, value, parents) VALUES (?, ?, ?)"
        cursor = await execute_query(query, (property_id, value, json.dumps(parents)))
        tag_id = cursor.lastrowid
    return await _get_tag_by_id(tag_id)


async def _get_tag(property_id, value):
    query = "SELECT * FROM tags WHERE property_id = ? AND value = ?"
    cursor = await execute_query(query, (property_id, value))
    row = cursor.fetchone()
    return _parse_tag_from_db(row)


async def _get_tag_by_id(tag_id: int):
    query = "SELECT * FROM tags WHERE id = ?"
    cursor = await execute_query(query, (str(tag_id),))
    row = cursor.fetchone()
    return _parse_tag_from_db(row)


def _parse_tag_from_db(row):
    if not row:
        return row
    else:
        _id, prop_id, value, parents = row
        parents = json.loads(parents)
        return Tag(id=_id, property_id=prop_id, value=value, parents=parents)


async def _get_tag_ancestors(tag: Tag, acc=[]):
    if tag.parents == [0]:
        return list({*tag.parents, *acc})
    else:
        acc = acc + tag.parents
        for parent in tag.parents:
            parent_tag = await _get_tag_by_id(parent)
            return await _get_tag_ancestors(parent_tag, acc)
