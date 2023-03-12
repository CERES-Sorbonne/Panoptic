# Connexion à la base de données SQLite
import json
import os
import sqlite3
from json import JSONDecodeError

from models import Tag, Image, Property

conn = sqlite3.connect(os.getenv('PANOPTIC_DB'))


# Fonction utilitaire pour exécuter une requête SQL et commettre les modifications
def execute_query(query: str, parameters: tuple = None):
    cursor = conn.cursor()
    if parameters:
        cursor.execute(query, parameters)
    else:
        cursor.execute(query)
    conn.commit()
    return cursor


def add_property(name: str, property_type: str) -> Property:
    query = 'INSERT INTO properties (name, type) VALUES (?, ?)'
    cursor = execute_query(query, (name, property_type))
    prop = Property(id=cursor.lastrowid, name=name, type=property_type)
    return prop


def add_tag(property_id: int, value: str, parents: str):
    query = "INSERT INTO tags (property_id, value, parents) VALUES (?, ?, ?)"
    cursor = execute_query(query, (property_id, value, parents))
    return cursor.lastrowid


def update_tag(tag: Tag):
    query = "UPDATE tags SET parents = ?, value = ?, color = ? WHERE id = ?"
    execute_query(query, (json.dumps(tag.parents), tag.value, tag.color, tag.id))


def add_image(sha1, height, width, name, extension, paths, url):
    query = """
        INSERT INTO images (sha1, height, width, name, extension, paths, url)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    execute_query(query, (sha1, height, width, name, extension, paths, url))


def get_image_by_sha1(sha1) -> [Image | None]:
    query = """
        SELECT *
        FROM images
        WHERE sha1 = ?
    """
    cursor = execute_query(query, (sha1,))
    image = cursor.fetchone()
    if image:
        return Image(**auto_dict(image, cursor))
    else:
        return None


def get_images():
    # requête à optimiser en deux requêtes ? pcke là on récupère les paths de l'image pour chaque property,
    # also peut être qu'il faut virer les champs de properties et on garde que l'id puisque que côté client on chope
    # les properties anyway
    query = """
            SELECT DISTINCT i.sha1, i.paths, i.height, i.width,  i.url, i.extension, i.name, p.id, p.name, p.type, i_d.value
            FROM images i
            LEFT JOIN images_properties i_d ON i.sha1 = i_d.sha1
            LEFT JOIN properties p ON i_d.property_id = p.id
            """
    cursor = execute_query(query)
    return cursor.fetchall()


def update_image_paths(sha1, new_paths) -> list[str]:
    query = """
               UPDATE images
               SET paths = ?
               WHERE sha1 = ?
           """
    execute_query(query, (new_paths, sha1))
    return new_paths


def add_image_property(sha1, property_id, value):
    query = """
            INSERT INTO images_properties (property_id, sha1, value)
            VALUES (?, ?, ?)
    """
    return execute_query(query, (property_id, sha1, json.dumps(value)))


def delete_image_property(property_id, sha1):
    query = 'DELETE FROM images_properties WHERE property_id = ? AND sha1 = ?'
    execute_query(query, (property_id, sha1))


def get_property_by_id(property_id) -> [Property|None]:
    query = """
            SELECT *
            FROM properties
            WHERE id = ?
        """
    cursor = execute_query(query, (property_id,))
    row = cursor.fetchone()
    if row:
        return Property(**auto_dict(row, cursor))
    else:
        return None


def get_tag(property_id, value):
    query = "SELECT * FROM tags WHERE property_id = ? AND value = ?"
    cursor = execute_query(query, (property_id, value))
    row = cursor.fetchone()
    return Tag(**auto_dict(row, cursor))


def get_tag_by_id(tag_id: int):
    query = "SELECT * FROM tags WHERE id = ?"
    cursor = execute_query(query, (str(tag_id),))
    row = cursor.fetchone()
    return Tag(**auto_dict(row, cursor))


def tag_in_ancestors(tag_id, parent_id) -> bool:
    if not parent_id:
        return False
    else:
        parent = get_tag_by_id(parent_id)
        ancestors = get_tag_ancestors(parent)
        if tag_id in ancestors:
            return True
    return False


def get_tag_ancestors(tag: Tag, acc=[]):
    if tag.parents == [0]:
        return list({*tag.parents, *acc})
    else:
        acc = acc + tag.parents
        for parent in tag.parents:
            parent_tag = get_tag_by_id(parent)
            return get_tag_ancestors(parent_tag, acc)


def auto_dict(row, cursor):
    return {key: decode_if_json(value) for key, value in zip([c[0] for c in cursor.description], row)}


def decode_if_json(value):
    try:
        return json.loads(value)
    except (TypeError, JSONDecodeError):
        return value


def get_tags(prop) -> list[Tag]:
    query = "SELECT * FROM tags "
    params = None
    if prop:
        query += "WHERE property_id = ?"
        params = (prop,)
    cursor = execute_query(query, params)
    return [Tag(**auto_dict(row, cursor)) for row in cursor.fetchall()]


def get_properties() -> list[Property]:
    query = "SELECT * from properties"
    cursor = execute_query(query)
    return [Property(**auto_dict(row, cursor)) for row in cursor.fetchall()]