# Connexion à la DB SQLite
from __future__ import annotations

import json
from typing import List, Any

import numpy as np
from pypika import Table, Parameter, PostgreSQLQuery, Order, functions

from panoptic.core.db.db_connection import DbConnection, db_lock
from panoptic.core.db.utils import auto_dict
from panoptic.models import Instance, ComputedValue, Vector, PluginDefaultParams, ActionParam, \
    VectorDescription, InstancePropertyValue, ImagePropertyValue
from panoptic.models import Tag, Property, Folder, Tab

Query = PostgreSQLQuery


class Db:
    def __init__(self, conn: DbConnection):
        if not conn.is_loaded:
            raise Exception('DbConnection is not started. Execute await conn.start() before')
        self.conn = conn

    async def close(self):
        await self.conn.conn.close()

    def get_project_path(self):
        return self.conn.folder_path

    # =====================================================
    # =================== Properties ======================
    # =====================================================

    @db_lock
    async def add_property(self, name: str, property_type: str, mode: str) -> Property:
        query = 'INSERT INTO properties (name, type, mode) VALUES (?, ?, ?) on conflict do nothing'
        cursor = await self.conn.execute_query(query, (name, property_type, mode))
        prop = Property(id=cursor.lastrowid, name=name, type=property_type, mode=mode)
        return prop

    @db_lock
    async def add_properties(self, properties: list[Property]) -> list[Property]:
        table = Table('properties')
        query = Query.into(table).columns('name', 'type', 'mode', )
        query = query.insert(*[(p.name, p.type, p.mode) for p in properties])
        await self.conn.execute_query(query.get_sql())

        added = await self.get_properties(last=len(properties))
        added.reverse()
        return added

    async def import_property(self, id_: int, name: str, property_type: str, mode: str) -> Property:
        query = 'INSERT INTO properties (id, name, type, mode) VALUES (?, ?, ?, ?) on conflict do nothing'
        cursor = await self.conn.execute_query(query, (id_, name, property_type, mode))
        prop = Property(id=cursor.lastrowid, name=name, type=property_type, mode=mode)
        return prop

    async def get_properties(self, last: int = None) -> list[Property]:
        query = "SELECT * from properties"
        if last:
            query += ' ORDER BY id DESC LIMIT ?'
            cursor = await self.conn.execute_query(query, (last,))
        else:
            cursor = await self.conn.execute_query(query)
        return [Property(**auto_dict(row, cursor)) for row in await cursor.fetchall()]

    async def get_property(self, property_id) -> [Property | None]:
        query = """
                SELECT *
                FROM properties
                WHERE id = ?
            """
        cursor = await self.conn.execute_query(query, (property_id,))
        row = await cursor.fetchone()
        if row:
            return Property(**auto_dict(row, cursor))
        else:
            return None

    async def update_property(self, new_property: Property):
        query = "UPDATE properties SET name = ? WHERE id = ?"
        await self.conn.execute_query(query, (new_property.name, new_property.id))

    async def delete_property(self, property_id):
        query = "DELETE from properties WHERE id = ?"
        await self.conn.execute_query(query, (property_id,))

    # =====================================================
    # =============== Property Values =====================
    # =====================================================

    async def get_instance_property_values(self, property_ids: List[int] = None, instance_ids: list[int] = None) \
            -> list[InstancePropertyValue]:
        values = Table('instance_property_values')
        query = Query.from_(values).select('*')

        if property_ids:
            query = query.where(values.property_id.isin(property_ids))

        if instance_ids:
            query = query.where(values.instance_id.isin(instance_ids))

        cursor = await self.conn.execute_query(query.get_sql())
        res = [InstancePropertyValue(**auto_dict(instance, cursor)) for instance in await cursor.fetchall()]
        return res

    async def get_image_property_values(self, property_ids: List[int] = None, sha1s: list[str] = None) \
            -> list[ImagePropertyValue]:
        values = Table('image_property_values')
        query = Query.from_(values).select('*')

        if property_ids:
            query = query.where(values.property_id.isin(property_ids))

        if sha1s:
            query = query.where(values.sha1.isin(sha1s))

        cursor = await self.conn.execute_query(query.get_sql())
        res = [ImagePropertyValue(**auto_dict(image, cursor)) for image in await cursor.fetchall()]
        return res

    async def set_instance_property_value(self, property_id: int, instance_ids: List[int], value: Any):
        json_value = json.dumps(value)
        t = Table('instance_property_values')
        query = Query.into(t).columns('property_id', 'instance_id', 'value')
        query = query.insert(*[(property_id, iid, json_value) for iid in instance_ids])
        query = query.get_sql() + ' ON CONFLICT (property_id, instance_id) DO UPDATE SET value=excluded.value'
        await self.conn.execute_query(query)
        return value

    async def set_image_property_value(self, property_id: int, sha1s: List[str], value: Any):
        json_value = json.dumps(value)

        t = Table('image_property_values')
        query = Query.into(t).columns('property_id', 'sha1', 'value')
        query = query.insert(*[(property_id, sha1, json_value) for sha1 in sha1s])
        query = query.get_sql() + ' ON CONFLICT (property_id, sha1) DO UPDATE SET value=excluded.value'
        await self.conn.execute_query(query)
        return value

    async def set_instance_property_array_values(self, property_id: int, instance_ids: list[int], values: list[Any]):
        """
            Allows to set different values to each instance.
        """
        t = Table('instance_property_values')
        query = Query.into(t).columns('property_id', 'instance_id', 'value')
        query = query.insert((property_id, Parameter('?'), Parameter('?')))
        query = query.get_sql() + ' ON CONFLICT (property_id, instance_id) DO UPDATE SET value=excluded.value'
        await self.conn.execute_query_many(query, [(idd, json.dumps(value)) for idd, value in
                                                   zip(instance_ids, values)])

    async def set_image_property_array_values(self, property_id: int, sha1s: list[str], values: list[Any]):
        """
            Allows to set different values to each image.
        """
        t = Table('image_property_values')
        query = Query.into(t).columns('property_id', 'sha1', 'value')
        query = query.insert((property_id, Parameter('?'), Parameter('?')))
        query = query.get_sql() + ' ON CONFLICT (property_id, sha1) DO UPDATE SET value=excluded.value'
        await self.conn.execute_query_many(query, [(sha1, json.dumps(value)) for sha1, value in
                                                   zip(sha1s, values)])

    async def delete_instance_property_value(self, property_id: int, instance_ids: list[int]):
        t = Table('instance_property_values')
        query = Query.from_(t).delete().where(t.property_id == property_id)
        query = query.where(t.instance_id.isin(instance_ids))
        await self.conn.execute_query(query.get_sql())
        return True

    async def delete_image_property_value(self, property_id: int, sha1s: list[str]):
        t = Table('image_property_values')
        query = Query.from_(t).delete().where(t.property_id == property_id)
        query = query.where(t.sha1.isin(sha1s))
        await self.conn.execute_query(query.get_sql())
        return True

    async def count_instance_values(self, instance_ids: list[int]):
        values = Table('instance_property_values')
        query = Query.from_(values).select('instance_id', functions.Count('*'))
        query = query.where(values.instance_id.isin(instance_ids))
        query = query.groupby(values.instance_id)
        print(query.get_sql())
        cursor = await self.conn.execute_query(query.get_sql())
        rows = await cursor.fetchall()
        res = {r[0]: r[1] for r in rows}
        # print(res)
        return res

    # =====================================================
    # ====================== Tag ==========================
    # =====================================================

    @db_lock
    async def add_tag(self, property_id: int, value: str, parents: str, color: int):
        query = "INSERT INTO tags (property_id, value, parents, color) VALUES (?, ?, ?, ?)"
        cursor = await self.conn.execute_query(query, (property_id, value, parents, color))
        return cursor.lastrowid

    @db_lock
    async def add_tags(self, tags: list[Tag]) -> list[Tag]:
        table = Table('tags')
        query = Query.into(table).columns('property_id', 'value', 'parents', 'color')
        query = query.insert(*[(p.property_id, p.value, json.dumps([0]), p.color) for p in tags])
        await self.conn.execute_query(query.get_sql())

        added = await self.get_last_tags(limit=len(tags))
        added.reverse()
        return added

    async def import_tag(self, id_: int, property_id: int, value: str, parents: str, color: int):
        query = "INSERT INTO tags (id, property_id, value, parents, color) VALUES (?, ?, ?, ?, ?)"
        cursor = await self.conn.execute_query(query, (id_, property_id, value, parents, color))
        return cursor.lastrowid

    async def get_tag_by_id(self, tag_id):
        query = "SELECT * FROM tags WHERE id = ?"
        cursor = await self.conn.execute_query(query, (tag_id,))
        row = await cursor.fetchone()
        if not row:
            return
        return Tag(**auto_dict(row, cursor))

    async def get_tag(self, property_id, value):
        query = "SELECT * FROM tags WHERE property_id = ? AND value = ?"
        cursor = await self.conn.execute_query(query, (property_id, value))
        row = await cursor.fetchone()
        if not row:
            return
        return Tag(**auto_dict(row, cursor))

    async def update_tag(self, tag: Tag):
        query = "UPDATE tags SET parents = ?, value = ?, color = ? WHERE id = ?"
        await self.conn.execute_query(query, (json.dumps(tag.parents), tag.value, tag.color, tag.id))

    async def set_tags_parents(self, links: list[tuple[int, list[int]]]):
        query = """
            UPDATE tags SET parents = ? WHERE id = ? ;
        """
        await self.conn.execute_query_many(query, [(json.dumps(p), c) for c, p in links])

    async def get_tag_ancestors(self, tag: Tag, acc=None):
        if not acc:
            acc = []
        if tag.parents == [0]:
            return list({*tag.parents, *acc})
        else:
            acc = acc + tag.parents
            for parent in tag.parents:
                if parent == 0:
                    continue
                parent_tag = await self.get_tag_by_id(parent)
                return await self.get_tag_ancestors(parent_tag, acc)

    async def get_tags(self, prop: int) -> list[Tag]:
        query = "SELECT * FROM tags "
        params = None
        if prop:
            query += "WHERE property_id = ?"
            params = (prop,)
        cursor = await self.conn.execute_query(query, params)
        return [Tag(**auto_dict(row, cursor)) for row in await cursor.fetchall()]

    async def get_last_tags(self, limit: int):
        query = "SELECT * FROM tags ORDER BY id DESC LIMIT ?"
        cursor = await self.conn.execute_query(query, (limit,))
        rows = await cursor.fetchall()
        if rows:
            return [Tag(**auto_dict(row, cursor)) for row in rows]
        return []

    async def delete_tag_by_id(self, tag_id: int) -> int:
        query = "DELETE FROM tags WHERE id = ?"
        await self.conn.execute_query(query, (tag_id,))
        return tag_id

    async def get_tags_by_parent_id(self, parent_id: int):
        query = "SELECT tags.* FROM tags, json_each(tags.parents) WHERE json_each.value = ?"
        cursor = await self.conn.execute_query(query, (parent_id,))
        return [Tag(**auto_dict(row, cursor)) for row in await cursor.fetchall()]

    async def tag_in_ancestors(self, tag_id, parent_id) -> bool:
        if not parent_id:
            return False
        else:
            parent = await self.get_tag_by_id(parent_id)
            ancestors = await self.get_tag_ancestors(parent)
            if tag_id in ancestors:
                return True
        return False

    # =====================================================
    # ================= Instances =========================
    # =====================================================

    @db_lock
    async def add_instance(self, folder_id: int, name: str, extension: str, sha1: str, url: str, width: int,
                           height: int,
                           ahash: str):
        table = Table('instances')
        query = Query.into(table).columns(
            'folder_id',
            'name',
            'extension',
            'sha1',
            'url',
            'width',
            'height',
            'ahash').insert((
            folder_id,
            name,
            extension,
            sha1,
            url,
            width,
            height,
            ahash))
        cursor = await self.conn.execute_query(query.get_sql())
        id_ = cursor.lastrowid

        return Instance(id=id_, folder_id=folder_id, name=name, extension=extension, sha1=sha1, url=url, width=width,
                        height=height)

    @db_lock
    async def add_instances(self, instances: list[Instance]):
        table = Table('instances')
        query = Query.into(table).columns(
            'folder_id',
            'name',
            'extension',
            'sha1',
            'url',
            'width',
            'height',
            'ahash')
        query = query.insert(*[(i.folder_id, i.name, i.extension, i.sha1, i.url, i.width, i.height, i.ahash) for i in instances])
        await self.conn.execute_query(query.get_sql())

        added = await self.get_instances(last=len(instances))
        added.reverse()
        return added

    async def import_instance(self, id_: int, folder_id: int, name: str, extension: str, sha1: str, url: str,
                              width: int,
                              height: int,
                              ahash: str):
        table = Table('instances')
        query = Query.into(table).columns(
            'id',
            'folder_id',
            'name',
            'extension',
            'sha1',
            'url',
            'width',
            'height',
            'ahash').insert((
            id_,
            folder_id,
            name,
            extension,
            sha1,
            url,
            width,
            height,
            ahash))
        cursor = await self.conn.execute_query(query.get_sql())

        return Instance(id=id_, folder_id=folder_id, name=name, extension=extension, sha1=sha1, url=url, width=width,
                        height=height)

    async def clone_instance(self, i: Instance):
        return await self.add_instance(i.folder_id, i.name, i.extension, i.sha1, i.url, i.width, i.height, i.ahash)

    async def get_instances(self, ids: List[int] = None, sha1s: List[str] = None, last: int = None):
        img_table = Table('instances')
        query = Query.from_(img_table).select('*')

        if ids:
            query = query.where(img_table.id.isin(ids))
        if sha1s:
            query = query.where(img_table.sha1.isin(sha1s))
        if last:
            query = query.orderby(img_table.id, order=Order.desc).limit(last)

        cursor = await self.conn.execute_query(query.get_sql())
        instance = [Instance(*instance) for instance in await cursor.fetchall()]
        return instance

    async def has_file(self, folder_id, name, extension):
        table = Table('instances')
        query = Query.from_(table).select('*').where(table.folder_id == folder_id)
        query = query.where(table.name == name).where(table.extension == extension).limit(1)

        cursor = await self.conn.execute_query(query.get_sql())
        res = await cursor.fetchone()
        if res:
            return Instance(*res)
        return False

    # =====================================================
    # ================== Folders ==========================
    # =====================================================

    async def add_folder(self, path: str, name: str, parent: int = None):
        query = 'INSERT INTO folders (path, name, parent) VALUES (?, ?, ?) ON CONFLICT(path) DO NOTHING'
        await self.conn.execute_query(query, (path, name, parent))
        cursor = await self.conn.execute_query('SELECT * FROM folders WHERE path = ?', (path,))
        row = await cursor.fetchone()
        folder = Folder(**auto_dict(row, cursor))
        return folder

    async def import_folder(self, id_: int, path: str, name: str, parent: int = None):
        query = 'INSERT INTO folders (id, path, name, parent) VALUES (?, ?, ?, ?) ON CONFLICT(path) DO NOTHING'
        await self.conn.execute_query(query, (id_, path, name, parent))
        cursor = await self.conn.execute_query('SELECT * FROM folders WHERE path = ?', (path,))
        row = await cursor.fetchone()
        folder = Folder(**auto_dict(row, cursor))
        return folder

    async def get_folders(self) -> List[Folder]:
        query = "SELECT * from folders"
        cursor = await self.conn.execute_query(query)
        return [Folder(**auto_dict(row, cursor)) for row in await cursor.fetchall()]

    async def get_folder(self, folder_id: int):
        table = Table('folders')
        query = Query.from_(table).select('*').where(table.id == folder_id)
        cursor = await self.conn.execute_query(query.get_sql())
        row = await cursor.fetchone()

        return Folder(**auto_dict(row, cursor))

    async def get_folder_by_path(self, path: str):
        table = Table('folders')
        query = Query.from_(table).select('*').where(table.path == path)
        cursor = await self.conn.execute_query(query.get_sql())
        row = await cursor.fetchone()
        if row:
            return Folder(**auto_dict(row, cursor))
        return None

    async def delete_folder(self, folder_id: int):
        query = "DELETE from folders WHERE id = ?"
        await self.conn.execute_query(query, (folder_id,))
        return folder_id

    # =====================================================
    # ================== UI TABS ==========================
    # =====================================================

    # async def add_tab(self, data):
    #     query = 'INSERT INTO tabs (data) VALUES (?)'
    #     cursor = await self.conn.execute_query(query, (json.dumps(data),))
    #     row = await cursor.fetchone()
    #     tab = Tab(id=cursor.lastrowid, data=data)
    #     return tab
    #
    # async def get_tabs(self) -> List[Tab]:
    #     query = "SELECT * from tabs"
    #     cursor = await self.conn.execute_query(query)
    #     return [Tab(**auto_dict(row, cursor)) for row in await cursor.fetchall()]
    #
    # async def update_tab(self, tab: Tab):
    #     query = "UPDATE tabs SET data = ? WHERE id = ?"
    #     await self.conn.execute_query(query, (json.dumps(tab.data), tab.id))
    #
    # async def delete_tab(self, tab_id: int):
    #     query = "DELETE from tabs WHERE id = ?"
    #     await self.conn.execute_query(query, (tab_id,))
    #     return tab_id

    # =====================================================
    # ================== Vectors ==========================
    # =====================================================

    async def add_vector(self, vector: Vector):
        query = f"""
            INSERT OR REPLACE INTO vectors (source, type, sha1, data)
            VALUES (?, ?, ?, ?);
        """
        await self.conn.execute_query(query, (vector.source, vector.type, vector.sha1, vector.data))
        return vector

    async def get_vectors(self, source: str, type_: str, sha1s: List[str] = None):
        t = Table('vectors')
        query = Query.from_(t).select('source', 'type', 'sha1', 'data')
        query = query.where(t.source == source).where(t.type == type_)
        if sha1s:
            query = query.where(t.sha1.isin(sha1s))
        cursor = await self.conn.execute_query(query.get_sql())
        rows = await cursor.fetchall()
        res = [Vector(*row) for row in rows]
        return res

    async def vector_exist(self, source: str, type_: str, sha1: str):
        t = Table('vectors')
        query = Query.from_(t).select('source', 'type', 'sha1')
        query = query.where(t.source == source).where(t.type == type_)
        query = query.where(t.sha1 == sha1)
        cursor = await self.conn.execute_query(query.get_sql())
        rows = await cursor.fetchall()
        if rows:
            return True
        return False

    async def get_vector_descriptions(self):
        query = """ 
        SELECT source, type, count(sha1) as count
        FROM vectors
        GROUP BY source, type;
        """
        cursor = await self.conn.execute_query(query)
        rows = await cursor.fetchall()
        if rows:
            return [VectorDescription(**auto_dict(r, cursor)) for r in rows]
        return []

    async def set_default_vector_id(self, vector_id: str):
        await self.conn.set_param('default_vector', vector_id)

    async def get_default_db_vector_id(self):
        await self.conn.get_param('default_vector')

    # =====================================================
    # ================== Plugins ==========================
    # =====================================================

    async def get_plugin_data(self, key: str):
        query = "SELECT * FROM plugin_data WHERE key=?"
        cursor = await self.conn.execute_query(query, (key,))
        row = await cursor.fetchone()
        if row:
            return json.loads(row[1])
        return None

    async def set_plugin_data(self, key: str, data):
        query = "INSERT OR REPLACE INTO plugin_data (key, value) VALUES (?, ?)"
        await self.conn.execute_query(query, (key, json.dumps(data)))
        return data

    # async def get_plugin_default_params(self, plugin_name: str):
    #     t = Table('plugin_defaults')
    #     query = Query.from_(t).select('name', 'base', 'functions')
    #     query = query.where(t.name == plugin_name)
    #     cursor = await self.conn.execute_query(query.get_sql())
    #     row = await cursor.fetchone()
    #     if row:
    #         return PluginDefaultParams(**auto_dict(row, cursor))
    #     return PluginDefaultParams(name=plugin_name)
    #
    # async def set_plugin_default_params(self, params: PluginDefaultParams):
    #     query = f"""
    #                 INSERT OR REPLACE INTO plugin_defaults (name, base, functions)
    #                 VALUES (?, ?, ?);
    #             """
    #     await self.conn.execute_query(query, (params.name, json.dumps(params.base), json.dumps(params.functions)))
    #     return params

    # =====================================================
    # ================== Actions ==========================
    # =====================================================

    # async def get_action_params(self):
    #     query = "SELECT * FROM action_params"
    #     cursor = await self.conn.execute_query(query)
    #     rows = await cursor.fetchall()
    #     if rows:
    #         return [ActionParam(**auto_dict(r, cursor)) for r in rows]
    #     return []
    #
    # async def get_action_param(self, name: str):
    #     query = "SELECT * FROM action_params WHERE name=?"
    #     cursor = await self.conn.execute_query(query, (name,))
    #     row = await cursor.fetchone()
    #     if row:
    #         return ActionParam(**auto_dict(row, cursor))
    #     return None
    #
    # async def set_action_param(self, update: ActionParam):
    #     print('update', update)
    #     query = f"""
    #                 INSERT OR REPLACE INTO action_params (name, value)
    #                 VALUES (?, ?);
    #             """
    #     await self.conn.execute_query(query, (update.name, update.value))
    #     return update

    # =====================================================
    # ================== UI_DATA ==========================
    # =====================================================

    async def get_ui_data(self, key: str):
        query = "SELECT * FROM ui_data WHERE key=?"
        cursor = await self.conn.execute_query(query, (key,))
        row = await cursor.fetchone()
        if row:
            return json.loads(row[1])
        return None

    async def get_all_ui_data(self):
        query = "SELECT * FROM ui_data"
        cursor = await self.conn.execute_query(query)
        rows = await cursor.fetchall()
        if rows:
            return {r[0]: json.loads(r[1]) for r in rows}
        return None

    async def set_ui_data(self, key: str, data):
        query = "INSERT OR REPLACE INTO ui_data (key, value) VALUES (?, ?)"
        await self.conn.execute_query(query, (key, json.dumps(data)))
        return data
