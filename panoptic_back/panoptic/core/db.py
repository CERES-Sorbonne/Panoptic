# Connexion à la base de données SQLite
import json
from typing import List

import numpy as np

from panoptic.core.db_utils import execute_query, decode_if_json, execute_query_many
from panoptic.models import ImageVector
from panoptic.models import Tag, Image, Property, ImageProperty, JSON, Folder, Tab


async def add_property(name: str, property_type: str) -> Property:
    query = 'INSERT INTO properties (name, type) VALUES (?, ?) on conflict do nothing'
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


async def get_images_by_sha1s(sha1_list: str | list[str]) -> [Image | list[Image] | None]:
    if type(sha1_list) == str:
        sha1_list = [sha1_list]
    query = """
        SELECT *
        FROM images
    """
    query += " WHERE sha1 in (" + ','.join('?' * len(sha1_list)) + ')'
    cursor = await execute_query(query, tuple(sha1_list))
    images = [Image(**auto_dict(image, cursor)) for image in await cursor.fetchall()]
    if len(images) > 1:
        return images
    elif len(images) == 1:
        return images[0]
    else:
        return None


async def get_full_image_with_sha1(sha1: str):
    query = """
            SELECT DISTINCT i.sha1, i.paths, i.height, i.width,  i.url, i.extension, i.name, i_d.property_id, i_d.value, i.ahash
            FROM images i
            LEFT JOIN images_properties i_d ON i.sha1 = i_d.sha1
            WHERE i.sha1 = ?
            """
    cursor = await execute_query(query, (sha1,))
    return await cursor.fetchall()


async def get_images(as_image=False):
    query = """
            SELECT DISTINCT i.sha1, i.paths, i.height, i.width,  i.url, i.extension, i.name, i_d.property_id, i_d.value, i.ahash
            FROM images i
            LEFT JOIN images_properties i_d ON i.sha1 = i_d.sha1
            ORDER BY i.name
            """
    cursor = await execute_query(query)
    if as_image:
        return [Image(**auto_dict(row, cursor)) for row in await cursor.fetchall()]
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
    query = "SELECT sha1, vector, ahash from images WHERE vector is not null "
    if image_list and len(image_list) > 0:
        query += " AND sha1 in (" + ','.join('?' * len(image_list)) + ')'
        cursor = await execute_query(query, tuple(image_list))
    else:
        cursor = await execute_query(query)
    return [ImageVector(**auto_dict(row, cursor)) for row in await cursor.fetchall()]


async def get_all_sha1() -> list[str]:
    query = "SELECT sha1 from images ORDER BY sha1"
    cursor = await execute_query(query)
    return [row for row in await cursor.fetchall()]


async def add_or_update_images_properties(sha1_list: list[str], property_id: int, value):
    query = "INSERT into images_properties (sha1, property_id, value) " \
            "VALUES (?, ?, ?)" \
            "ON conflict (sha1, property_id) do update set value=excluded.value"
    svalue = json.dumps(value)
    return await execute_query_many(query, [(sha1, property_id, svalue) for sha1 in sha1_list])


async def get_sha1s_by_filenames(filenames: list[str]) -> list[str]:
    query = "SELECT sha1 from images where name in " + "(" + ','.join('?' * len(filenames)) + ') order by name'
    cursor = await execute_query(query, tuple(filenames))
    return await cursor.fetchall()