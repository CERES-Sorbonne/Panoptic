# Connexion à la base de données SQLite
import json
from typing import List, Any

import numpy as np
from pypika import Table, Parameter, PostgreSQLQuery

from panoptic.core.db_utils import execute_query, decode_if_json, execute_query_many
from panoptic.models import PropertyValue2, Image2, ComputedValue
from panoptic.models import Tag, Property, Folder, Tab

Query = PostgreSQLQuery


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


async def add_image(folder_id: int, name: str, extension: str, sha1: str, url: str, width: int, height: int):
    table = Table('images')
    query = Query.into(table).columns(
        'folder_id',
        'name',
        'extension',
        'sha1',
        'url',
        'width',
        'height').insert(
        folder_id,
        name,
        extension,
        sha1,
        url,
        width,
        height
    )
    cursor = await execute_query(query.get_sql())
    id_ = cursor.lastrowid

    return Image2(id=id_, folder_id=folder_id, name=name, extension=extension, sha1=sha1, url=url, width=width,
                  height=height)


async def has_image_file(folder_id, name, extension):
    table = Table('images')
    query = Query.from_(table).select('*').where(table.folder_id == folder_id)
    query = query.where(table.name == name).where(table.extension == extension).limit(1)

    cursor = await execute_query(query.get_sql())
    res = await cursor.fetchone()
    if res:
        return Image2(*res)
    return False


async def get_images(ids: List[int] = None, sha1s: List[str] = None):
    img_table = Table('images')
    query = Query.from_(img_table).select('*')

    if ids:
        query = query.where(img_table.id.isin(ids))
    if sha1s:
        query = query.where(img_table.sha1.isin(sha1s))

    cursor = await execute_query(query.get_sql())
    images = [Image2(*image) for image in await cursor.fetchall()]
    return images


async def get_property_values(property_ids: List[int] = None, image_ids: List[int] = None, sha1s: List[str] = None):
    values = Table('property_values')
    query = Query.from_(values).select('*')

    if property_ids:
        query = query.where(values.property_id.isin(property_ids))

    if image_ids:
        query = query.where(values.image_id.isin(image_ids))
    elif sha1s:
        query = query.where(values.sha1.isin(sha1s))

    cursor = await execute_query(query.get_sql())
    res = [PropertyValue2(**auto_dict(image, cursor)) for image in await cursor.fetchall()]
    return res


async def delete_property_value(property_id, image_id: int):
    query = 'DELETE FROM property_values WHERE property_id = ? AND image_id = ?'
    await execute_query(query, (property_id, image_id))


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


async def get_folders() -> List[Folder]:
    query = "SELECT * from folders"
    cursor = await execute_query(query)
    return [Folder(**auto_dict(row, cursor)) for row in await cursor.fetchall()]


async def get_folder(folder_id: int):
    table = Table('folders')
    query = Query.from_(table).select('*').where(table.id == folder_id)
    cursor = await execute_query(query.get_sql())
    row = await cursor.fetchone()

    return Folder(**auto_dict(row, cursor))


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


async def get_property_values_with_tag(tag_id: int) -> list[PropertyValue2]:
    query = "SELECT * from property_values where value like ?"
    cursor = await execute_query(query, (f"[%{tag_id}%]",))
    return [PropertyValue2(**auto_dict(row, cursor)) for row in await cursor.fetchall()]


async def set_property_values(property_id: int, value: Any, image_ids: List[int]):
    query = "INSERT into property_values (property_id, image_id, sha1, value) " \
            "VALUES (?, ?, ?, ?)" \
            "ON conflict (property_id, image_id, sha1) do update set value=excluded.value"
    svalue = json.dumps(value)
    print(f"{property_id}: {svalue}: {image_ids}")
    return await execute_query_many(query, [(property_id, image_id, '', svalue) for image_id in image_ids])


async def set_computed_value(sha1: str, ahash: str, vector: np.array):
    t = Table('computed_values')
    query = Query.into(t).columns('sha1', 'ahash', 'vector').insert(sha1, ahash, Parameter('?'))
    query = query.on_conflict('sha1').do_update('vector', Parameter('?'))
    # query = query.get_sql() + " ON CONFLICT(sha1) DO NOTHING"
    await execute_query(query.get_sql(), (vector, vector))
    return ComputedValue(sha1, ahash, vector)


async def get_sha1s_by_filenames(filenames: list[str]) -> list[str]:
    query = "SELECT sha1 from images where name in " + "(" + ','.join('?' * len(filenames)) + ') order by name'
    cursor = await execute_query(query, tuple(filenames))
    return await cursor.fetchall()


async def vacuum():
    query = "VACUUM"
    await execute_query(query)


async def get_sha1_ahashs(sha1s: list[str] = None):
    t = Table('computed_values')
    query = Query.from_(t).select('sha1', 'ahash')
    if sha1s:
        query = query.where(t.sha1.isin(sha1s))
    cursor = await execute_query(query.get_sql())
    rows = await cursor.fetchall()
    res = {row[0]: row[1] for row in rows}
    return res


async def get_sha1_computed_values(sha1s: list[str] = None):
    t = Table('computed_values')
    # select query should be in same order as the dataclass model properties
    query = Query.from_(t).select('sha1', 'ahash', 'vector')
    if sha1s:
        query = query.where(t.sha1.isin(sha1s))
    cursor = await execute_query(query.get_sql())
    rows = await cursor.fetchall()
    res = [ComputedValue(*row) for row in rows]
    return res
