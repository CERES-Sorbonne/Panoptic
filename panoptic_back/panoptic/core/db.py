# Connexion à la base de données SQLite
import json
from typing import List

import numpy as np

from panoptic.core.db_utils import execute_query, decode_if_json
from panoptic.models import ImageVector
from panoptic.models import Tag, Image, Property, ImageProperty, JSON, Folder, Tab


async def add_property(name: str, property_type: str) -> Property:
    query = 'INSERT INTO properties (name, type) VALUES (?, ?)'
    cursor = await execute_query(query, (name, property_type))
    prop = Property(id=cursor.lastrowid, name=name, type=property_type)
    return prop


async def add_tag(property_id: int, value: str, parents: str, color: str):
    query = "INSERT INTO tags (property_id, value, parents, color) VALUES (?, ?, ?, ?)"
    cursor = await execute_query(query, (property_id, value, parents, color))
    return cursor.lastrowid


async def update_tag(tag: Tag):
    query = "UPDATE tags SET parents = ?, value = ?, color = ? WHERE id = ?"
    await execute_query(query, (json.dumps(tag.parents), tag.value, tag.color, tag.id))


async def add_image(sha1, height, width, name, extension, paths, url):
    query = """
        INSERT INTO images (sha1, height, width, name, extension, paths, url)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    await execute_query(query, (sha1, height, width, name, extension, paths, url))


async def get_image_by_sha1(sha1) -> [Image | None]:
    query = """
        SELECT *
        FROM images
        WHERE sha1 = ?
    """
    cursor = await execute_query(query, (sha1,))
    image = await cursor.fetchone()
    if image:
        return Image(**auto_dict(image, cursor))
    else:
        return None


async def get_images():
    query = """
            SELECT DISTINCT i.sha1, i.paths, i.height, i.width,  i.url, i.extension, i.name, i_d.property_id, i_d.value, i.ahash
            FROM images i
            LEFT JOIN images_properties i_d ON i.sha1 = i_d.sha1
            """
    cursor = await execute_query(query)
    return await cursor.fetchall()


async def update_image_paths(sha1, new_paths) -> list[str]:
    query = """
               UPDATE images
               SET paths = ?
               WHERE sha1 = ?
           """
    await execute_query(query, (new_paths, sha1))
    return new_paths


async def update_image_hashs(sha1, ahash: str, vector: np.array):
    query = """UPDATE images SET ahash = ?, vector= ? WHERE sha1 = ?"""
    await execute_query(query, (ahash, vector, sha1))


async def add_image_property(sha1, property_id, value):
    query = """
            INSERT INTO images_properties (property_id, sha1, value)
            VALUES (?, ?, ?)
    """
    return await execute_query(query, (property_id, sha1, json.dumps(value)))


async def delete_image_property(property_id, sha1):
    query = 'DELETE FROM images_properties WHERE property_id = ? AND sha1 = ?'
    await execute_query(query, (property_id, sha1))


async def get_property_by_id(property_id) -> [Property | None]:
    query = """
            SELECT *
            FROM properties
            WHERE id = ?
        """
    cursor = await execute_query(query, (property_id,))
    row = await cursor.fetchone()
    if row:
        return Property(**auto_dict(row, cursor))
    else:
        return None


async def get_tag(property_id, value):
    query = "SELECT * FROM tags WHERE property_id = ? AND value = ?"
    cursor = await execute_query(query, (property_id, value))
    row = await cursor.fetchone()
    if not row:
        return
    return Tag(**auto_dict(row, cursor))


async def get_tag_ancestors(tag: Tag, acc=None):
    if not acc:
        acc = []
    if tag.parents == [0]:
        return list({*tag.parents, *acc})
    else:
        acc = acc + tag.parents
        for parent in tag.parents:
            if parent == 0:
                continue
            parent_tag = await get_tag_by_id(parent)
            return await get_tag_ancestors(parent_tag, acc)


def auto_dict(row, cursor):
    return {key: decode_if_json(value) for key, value in zip([c[0] for c in cursor.description], row)}


async def get_tags(prop) -> list[Tag]:
    query = "SELECT * FROM tags "
    params = None
    if prop:
        query += "WHERE property_id = ?"
        params = (prop,)
    cursor = await execute_query(query, params)
    return [Tag(**auto_dict(row, cursor)) for row in await cursor.fetchall()]


async def get_tag_by_id(tag_id: int):
    query = "SELECT * FROM tags WHERE id = ?"
    cursor = await execute_query(query, (tag_id,))
    row = await cursor.fetchone()
    if row:
        return Tag(**auto_dict(row, cursor))
    return None


async def delete_tag_by_id(tag_id: int) -> int:
    query = "DELETE FROM tags WHERE id = ?"
    await execute_query(query, (tag_id,))
    return tag_id


async def get_tags_by_parent_id(parent_id: int):
    query = "SELECT tags.* FROM tags, json_each(tags.parents) WHERE json_each.value = ?"
    cursor = await execute_query(query, (parent_id,))
    return [Tag(**auto_dict(row, cursor)) for row in await cursor.fetchall()]


async def tag_in_ancestors(tag_id, parent_id) -> bool:
    if not parent_id:
        return False
    else:
        parent = await get_tag_by_id(parent_id)
        ancestors = await get_tag_ancestors(parent)
        if tag_id in ancestors:
            return True
    return False


async def get_properties() -> list[Property]:
    query = "SELECT * from properties"
    cursor = await execute_query(query)
    return [Property(**auto_dict(row, cursor)) for row in await cursor.fetchall()]


async def get_image_property(sha1: str, property_id: int) -> ImageProperty | None:
    query = "SELECT * from images_properties WHERE sha1 = ? AND property_id = ?"
    cursor = await execute_query(query, (sha1, property_id))
    row = await cursor.fetchone()
    if not row:
        return None
    return ImageProperty(**auto_dict(row, cursor))


async def update_image_property(sha1: str, property_id: int, value: JSON) -> str:
    query = "UPDATE images_properties SET value = ? WHERE sha1 = ? AND property_id = ?"
    await execute_query(query, (json.dumps(value), sha1, property_id))
    return decode_if_json(value)


async def get_folders() -> List[Folder]:
    query = "SELECT * from folders"
    cursor = await execute_query(query)
    return [Folder(**auto_dict(row, cursor)) for row in await cursor.fetchall()]


async def get_tabs() -> List[Tab]:
    query = "SELECT * from tabs"
    cursor = await execute_query(query)
    return [Tab(**auto_dict(row, cursor)) for row in await cursor.fetchall()]


async def add_folder(path: str, name: str, parent: int = None):
    query = 'INSERT INTO folders (path, name, parent) VALUES (?, ?, ?) ON CONFLICT(path) DO NOTHING'
    await execute_query(query, (path, name, parent))
    cursor = await execute_query('SELECT * FROM folders WHERE path = ?', (path,))
    row = await cursor.fetchone()
    folder = Folder(**auto_dict(row, cursor))
    return folder


async def delete_folder(folder_id: int):
    query = "DELETE from folders WHERE id = ?"
    await execute_query(query, (folder_id,))
    return folder_id


async def add_tab(name: str, data):
    query = 'INSERT INTO tabs (name, data) VALUES (?,?)'
    cursor = await execute_query(query, (name, json.dumps(data)))
    row = await cursor.fetchone()
    folder = Tab(id=cursor.lastrowid, name=name, data=data)
    return folder


async def update_tab(tab: Tab):
    query = "UPDATE tabs SET name = ?, data = ? WHERE id = ?"
    await execute_query(query, (tab.name, json.dumps(tab.data), tab.id))


async def delete_tab(tab_id: int):
    query = "DELETE from tabs WHERE id = ?"
    await execute_query(query, (tab_id,))
    return tab_id


async def delete_property(property_id):
    query = "DELETE from properties WHERE id = ?"
    await execute_query(query, (property_id,))


async def update_property(new_property: Property):
    query = "UPDATE properties SET name = ?, type = ? WHERE id = ?"
    await execute_query(query, (new_property.name, new_property.type, new_property.id))


async def get_image_properties_with_tag(tag_id: int) -> list[ImageProperty]:
    query = "SELECT * from images_properties ip where ip.value like ?"
    cursor = await execute_query(query, (f"[%{tag_id}%]",))
    return [ImageProperty(**auto_dict(row, cursor)) for row in await cursor.fetchall()]


async def get_images_with_vectors(image_list: list[str] = None):
    query = "SELECT sha1, vector, ahash from images"
    if image_list and len(image_list) > 0:
        query += " WHERE sha1 in (" + ','.join('?' * len(image_list)) + ')'
        cursor = await execute_query(query, tuple(image_list))
    else:
        cursor = await execute_query(query)
    return [ImageVector(**auto_dict(row, cursor)) for row in await cursor.fetchall()]


async def get_all_sha1() -> list[str]:
    query = "SELECT sha1 from images ORDER BY sha1"
    cursor = await execute_query(query)
    return [row for row in await cursor.fetchall()]