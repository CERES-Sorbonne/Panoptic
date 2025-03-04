# Connexion à la DB SQLite
from __future__ import annotations

import asyncio
import io
import json
from typing import List

from pypika import Table, PostgreSQLQuery, Order, functions

from panoptic.core.db.db_connection import DbConnection, db_lock
from panoptic.core.db.utils import auto_dict, decode_if_json
from panoptic.models import Instance, Vector, VectorDescription, InstanceProperty, ImageProperty, \
    InstancePropertyKey, ImagePropertyKey, PropertyType, PropertyMode, PropertyGroup
from panoptic.models import Tag, Property, Folder

Query = PostgreSQLQuery


class Db:
    def __init__(self, conn: DbConnection):
        if not conn.is_loaded:
            raise Exception('DbConnection is not started. Execute await conn.start() before')
        self.conn = conn

        self._last_instance_id = 0
        self._last_property_id = 0
        self._last_tag_id = 0

        self.property_group_id_lock = asyncio.Lock()

    async def close(self):
        await self.conn.conn.close()

    def get_project_path(self):
        return self.conn.folder_path

    # =====================================================
    # ====================== IDs ==========================
    # =====================================================

    @db_lock
    async def get_new_instance_ids(self, nb: int):
        last_id = self._last_instance_id

        query = "SELECT id FROM instances ORDER BY id DESC LIMIT 1"
        cursor = await self.conn.execute_query(query)
        res = await cursor.fetchone()
        if res:
            last_id = res[0]
        ids = [last_id + i + 1 for i in range(nb)]
        self._last_instance_id = ids[-1]
        return ids

    @db_lock
    async def get_new_property_ids(self, nb: int):
        last_id = self._last_property_id

        query = "SELECT id FROM properties ORDER BY id DESC LIMIT 1"
        cursor = await self.conn.execute_query(query)
        res = await cursor.fetchone()
        if res:
            last_id = res[0]
        ids = [last_id + i + 1 for i in range(nb)]
        self._last_property_id = ids[-1]
        return ids

    @db_lock
    async def get_new_tag_ids(self, nb: int):
        last_id = self._last_tag_id

        query = "SELECT id FROM tags ORDER BY id DESC LIMIT 1"
        cursor = await self.conn.execute_query(query)
        res = await cursor.fetchone()
        if res:
            last_id = res[0]
        ids = [last_id + i + 1 for i in range(nb)]
        self._last_tag_id = ids[-1]
        return ids

    # =====================================================
    # =================== Properties ======================
    # =====================================================

    async def import_properties(self, properties: list[Property]) -> list[Property]:
        fake_ids = [i for i in properties if i.id < 0]
        if fake_ids:
            real_ids = await self.get_new_property_ids(len(fake_ids))
            for prop, id_ in zip(fake_ids, real_ids):
                prop.id = id_

        query = """
        INSERT INTO properties (id, name, type, mode, property_group_id) VALUES (?, ?, ?, ?, ?) 
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name,
            type=excluded.type,
            mode=excluded.mode,
            property_group_id=excluded.property_group_id
        """
        values = [
            (p.id, p.name, p.type.value, p.mode.value, p.property_group_id) for p in properties
        ]
        await self.conn.execute_query_many(query, values)
        return properties

    async def get_properties(self, ids: list[int] = None) -> list[Property]:
        table = Table('properties')
        query = Query.from_(table).select('*')
        if ids:
            query = query.where(table.id.isin(ids))
        cursor = await self.conn.execute_query(query.get_sql())
        rows = await cursor.fetchall()
        if rows:
            properties = [Property(row[0], row[1], PropertyType(row[2]), PropertyMode(row[3]), row[4]) for row in rows]
            return properties
        return []

    async def get_property(self, property_id) -> Property | None:
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

    async def delete_property(self, property_id):
        query = "DELETE from properties WHERE id = ?"
        await self.conn.execute_query(query, (property_id,))

    # =====================================================
    # =============== Property Values =====================
    # =====================================================

    async def get_instance_values_count(self):
        query = "SELECT count(*) FROM instance_property_values;"
        cursor = await self.conn.execute_query(query)
        row = await cursor.fetchone()
        if row:
            return row[0]

    async def get_image_values_count(self):
        query = "SELECT count(*) FROM image_property_values;"
        cursor = await self.conn.execute_query(query)
        row = await cursor.fetchone()
        if row:
            return row[0]

    async def get_instance_property_values(self, property_ids: List[int] = None, instance_ids: list[int] = None) \
            -> list[InstanceProperty]:
        values = Table('instance_property_values')
        query = Query.from_(values).select('*')

        if property_ids:
            query = query.where(values.property_id.isin(property_ids))

        if instance_ids:
            query = query.where(values.instance_id.isin(instance_ids))

        cursor = await self.conn.execute_query(query.get_sql())
        res = [InstanceProperty(**auto_dict(instance, cursor)) for instance in await cursor.fetchall()]
        return res

    async def get_instance_property_values_from_keys(self, keys: list[InstancePropertyKey]) \
            -> list[InstanceProperty]:

        chunk_size = 500
        res = []
        query = 'SELECT * FROM instance_property_values WHERE '
        chunked_keys = [keys[i:i + chunk_size] for i in range(0, len(keys), chunk_size)]

        for chunk in chunked_keys:
            conditions = ' OR '.join(['(property_id = ? AND instance_id = ?)'] * len(chunk))
            full_query = query + conditions
            params = [p for k in chunk for p in (k.property_id, k.instance_id)]
            cursor = await self.conn.execute_query(full_query, tuple(params))
            res.extend([InstanceProperty(**auto_dict(value, cursor)) for value in await cursor.fetchall()])
        return res

    async def get_image_property_values(self, property_ids: List[int] = None, sha1s: list[str] = None) \
            -> list[ImageProperty]:
        values = Table('image_property_values')
        query = Query.from_(values).select('*')

        if property_ids:
            query = query.where(values.property_id.isin(property_ids))

        if sha1s:
            query = query.where(values.sha1.isin(sha1s))

        cursor = await self.conn.execute_query(query.get_sql())
        res = [ImageProperty(**auto_dict(image, cursor)) for image in await cursor.fetchall()]
        return res

    async def get_image_property_values_from_keys(self, keys: list[ImagePropertyKey]) \
            -> list[ImageProperty]:
        chunk_size = 500
        res = []
        query = 'SELECT * FROM image_property_values WHERE '
        chunked_keys = [keys[i:i + chunk_size] for i in range(0, len(keys), chunk_size)]

        for chunk in chunked_keys:
            conditions = ' OR '.join(['(property_id = ? AND sha1 = ?)'] * len(chunk))
            full_query = query + conditions
            params = [p for k in chunk for p in (k.property_id, k.sha1)]
            cursor = await self.conn.execute_query(full_query, tuple(params))
            res.extend([ImageProperty(**auto_dict(value, cursor)) for value in await cursor.fetchall()])
        return res

    async def stream_instance_property_values(self, position: int, chunk_size: int):
        query = """
        SELECT * FROM instance_property_values
        WHERE rowid > ?
        ORDER BY rowid ASC
        LIMIT ?;
        """
        cursor = await self.conn.execute_query(query, (position, chunk_size))
        rows = await cursor.fetchall()
        if rows:
            return [InstanceProperty(**auto_dict(row, cursor)) for row in rows]
        return []

    async def stream_image_property_values(self, position: int, chunk_size: int):
        query = """
        SELECT * FROM image_property_values
        WHERE rowid > ?
        ORDER BY rowid ASC
        LIMIT ?;
        """
        cursor = await self.conn.execute_query(query, (position, chunk_size))
        rows = await cursor.fetchall()
        if rows:
            return [ImageProperty(**auto_dict(row, cursor)) for row in rows]
        return []

    async def import_instance_property_values(self, values: list[InstanceProperty]):
        query = "INSERT OR REPLACE INTO instance_property_values (property_id, instance_id, value) VALUES (?, ?, ?)"
        await self.conn.execute_query_many(query, [(v.property_id, v.instance_id, json.dumps(v.value)) for v in values])
        return values

    async def import_image_property_values(self, values: list[ImageProperty]):
        query = "INSERT OR REPLACE INTO image_property_values (property_id, sha1, value) VALUES (?, ?, ?)"
        await self.conn.execute_query_many(query, [(v.property_id, v.sha1, json.dumps(v.value)) for v in values])
        return values

    async def delete_instance_property_values(self, values: list[InstancePropertyKey]):
        query = "DELETE FROM instance_property_values WHERE property_id = ? AND instance_id = ?"
        await self.conn.execute_query_many(query, [(v.property_id, v.instance_id) for v in values])
        return True

    async def delete_image_property_values(self, values: list[ImagePropertyKey]):
        query = "DELETE FROM image_property_values WHERE property_id = ? AND sha1 = ?"
        await self.conn.execute_query_many(query, [(v.property_id, v.sha1) for v in values])
        return True

    async def count_instance_values(self, instance_ids: list[int]):
        values = Table('instance_property_values')
        query = Query.from_(values).select('instance_id', functions.Count('*'))
        query = query.where(values.instance_id.isin(instance_ids))
        query = query.groupby(values.instance_id)
        cursor = await self.conn.execute_query(query.get_sql())
        rows = await cursor.fetchall()
        res = {r[0]: r[1] for r in rows}
        # print(res)
        return res

    async def delete_image_values(self, sha1s: list[str]):
        query = "DELETE FROM image_property_values WHERE sha1 = ?"
        await self.conn.execute_query_many(query, [(sha1,) for sha1 in sha1s])
        return True

    # =====================================================
    # ====================== Tag ==========================
    # =====================================================

    async def import_tags(self, tags: list[Tag]):
        fake_ids = [t for t in tags if t.id < 0]
        if fake_ids:
            real_ids = await self.get_new_tag_ids(len(fake_ids))
            for tag, id_ in zip(fake_ids, real_ids):
                tag.id = id_

        query = "INSERT OR REPLACE INTO tags (id, property_id, value, parents, color) VALUES (?, ?, ?, ?, ?)"
        await self.conn.execute_query_many(query, [(t.id, t.property_id, t.value, json.dumps(t.parents),
                                                    t.color) for t in tags])
        return tags

    async def get_tag_by_id(self, tag_id):
        query = "SELECT * FROM tags WHERE id = ?"
        cursor = await self.conn.execute_query(query, (tag_id,))
        row = await cursor.fetchone()
        if not row:
            return
        return Tag(**auto_dict(row, cursor))

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

    async def get_tags(self, prop: int = None) -> list[Tag]:
        query = "SELECT * FROM tags "
        params = None
        if prop:
            query += "WHERE property_id = ?"
            params = (prop,)
        cursor = await self.conn.execute_query(query, params)
        return [Tag(**auto_dict(row, cursor)) for row in await cursor.fetchall()]

    async def get_tags_by_ids(self, ids: list[int]):
        table = Table('tags')
        query = Query.from_(table).select('*').where(table.id.isin(ids))
        cursor = await self.conn.execute_query(query.get_sql())
        rows = await cursor.fetchall()
        if rows:
            tags = [Tag(**auto_dict(row, cursor)) for row in rows]
            return tags
        return []

    async def delete_tag_by_id(self, tag_id: int) -> int:
        query = "DELETE FROM tags WHERE id = ?"
        await self.conn.execute_query(query, (tag_id,))
        return tag_id

    # =====================================================
    # ==================== Images =========================
    # =====================================================

    async def import_image(self, sha1: str, small: bytes, medium: bytes, large: bytes):
        query = "INSERT OR REPLACE INTO images (sha1, small, medium, large) VALUES (?, ?, ?, ?)"
        await self.conn.execute_query(query, (sha1, small, medium, large))
        return sha1, small, medium, large

    async def get_small_image(self, sha1: str):
        query = "SELECT small FROM images WHERE sha1=?"
        cursor = await self.conn.execute_query(query, (sha1,))
        row = await cursor.fetchone()
        if not row:
            return row
        return row[0]

    async def get_medium_image(self, sha1: str):
        query = "SELECT medium FROM images WHERE sha1=?"
        cursor = await self.conn.execute_query(query, (sha1,))
        row = await cursor.fetchone()
        if not row:
            return row
        return row[0]

    async def get_large_image(self, sha1: str):
        query = "SELECT large FROM images WHERE sha1=?"
        cursor = await self.conn.execute_query(query, (sha1,))
        row = await cursor.fetchone()
        if not row:
            return row
        return row[0]

    async def get_raw_image(self, sha1: str):
        query = "SELECT raw FROM images WHERE sha1=?"
        cursor = await self.conn.execute_query(query, (sha1,))
        row = await cursor.fetchone()
        if not row:
            return row
        return row[0]

    async def has_image(self, sha1: str):
        query = "SELECT sha1 FROM images WHERE sha1=?"
        cursor = await self.conn.execute_query(query, (sha1,))
        row = await cursor.fetchone()
        if not row:
            return False
        return True

    async def delete_large_images(self):
        query = "UPDATE images SET large = NULL"
        await self.conn.execute_query(query)

    async def delete_medium_images(self):
        query = "UPDATE images SET medium = NULL"
        await self.conn.execute_query(query)

    async def delete_small_images(self):
        query = "UPDATE images SET small = NULL"
        await self.conn.execute_query(query)

    async def delete_images(self, sha1s: list[str]):
        query = "DELETE FROM images WHERE sha1 = ?"
        await self.conn.execute_query_many(query, [(sha1,) for sha1 in sha1s])

    # =====================================================
    # ================= Instances =========================
    # =====================================================

    async def get_instances_count(self):
        query = "SELECT count(*) FROM instances;"
        cursor = await self.conn.execute_query(query)
        row = await cursor.fetchone()
        if row:
            return row[0]

    async def import_instances(self, instances: list[Instance]):
        fake_ids = [i for i in instances if i.id < 0]
        if fake_ids:
            real_ids = await self.get_new_instance_ids(len(fake_ids))
            for instance, id_ in zip(fake_ids, real_ids):
                instance.id = id_

        query = "INSERT OR REPLACE INTO instances (id,folder_id,name,extension,sha1,url,width,height,ahash) VALUES " \
                "(?,?,?,?,?,?,?,?,?)"
        values = [
            (i.id, i.folder_id, i.name, i.extension, i.sha1, i.url, i.width, i.height, i.ahash) for i in instances
        ]
        await self.conn.execute_query_many(query, values)
        return instances

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

    async def stream_instances(self, position: int, chunk_size: int):
        query = """
        SELECT * FROM instances
        WHERE rowid > ?
        ORDER BY rowid ASC
        LIMIT ?;
        """
        cursor = await self.conn.execute_query(query, (position, chunk_size))
        rows = await cursor.fetchall()
        if rows:
            return [Instance(*row) for row in rows]
        return []

    async def get_instance_sha1_and_url(self):
        query = "SELECT sha1, url FROM instances"
        cursor = await self.conn.execute_query(query)
        rows = await cursor.fetchall()
        if rows:
            return rows
        return []

    async def has_file(self, folder_id, name, extension):
        table = Table('instances')
        query = Query.from_(table).select('*').where(table.folder_id == folder_id)
        query = query.where(table.name == name).where(table.extension == extension).limit(1)

        cursor = await self.conn.execute_query(query.get_sql())
        res = await cursor.fetchone()
        if res:
            return Instance(*res)
        return False

    async def get_all_instances_ids(self):
        query = 'SELECT id FROM instances'
        cursor = await self.conn.execute_query(query)
        res = await cursor.fetchall()
        if res:
            return {r[0] for r in res}
        else:
            return set()

    async def get_all_instance_sha1s(self):
        query = 'SELECT sha1 FROM instances'
        cursor = await self.conn.execute_query(query)
        res = await cursor.fetchall()
        if res:
            return {r[0] for r in res}
        else:
            return set()

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

    async def delete_vectors(self, sha1s: list[str]):
        query = "DELETE FROM vectors WHERE sha1 = ?"
        await self.conn.execute_query_many(query, [(sha1,) for sha1 in sha1s])

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

    async def get_project_param(self, key: str):
        query = f'SELECT value FROM project WHERE key="{key}";'
        cursor = await self.conn.execute_query(query)
        row = await cursor.fetchone()
        if row:
            return decode_if_json(row[0])
        return None

    async def set_project_param(self, key: str, value: str):
        query = f"""
                        INSERT OR REPLACE INTO project (key, value)
                        VALUES (?,?);
                """
        cursor = await self.conn.execute_query(query, (key, json.dumps(value)))
        return cursor

    # =====================================================
    # ================ PROPERTY GROUPS ====================
    # =====================================================

    async def get_property_groups(self):
        query = "SELECT * FROM property_group"
        cursor = await self.conn.execute_query(query)
        rows = await cursor.fetchall()
        if rows:
            return [PropertyGroup(*row) for row in rows]
        return None

    async def import_property_groups(self, groups: list[PropertyGroup]):
        query = "INSERT OR REPLACE INTO property_group (id, name) VALUES (?, ?)"
        await self.conn.execute_query_many(query, [(g.id, g.name) for g in groups])
        return groups

    async def delete_property_groups(self, groups: list[int]):
        query = "DELETE FROM property_group WHERE id=?;"
        await self.conn.execute_query_many(query, [(i,) for i in groups])

    # =====================================================
    # ==================== ID COUNTERS ====================
    # =====================================================

    async def _get_id_counter_helper(self, counter_name: str, nb: int):
        query = f"SELECT next FROM id_counter WHERE name='{counter_name}';"
        cursor = await self.conn.execute_query(query)
        row = await cursor.fetchone()
        next_id = row[0]

        update = "INSERT OR REPLACE INTO id_counter VALUES (?,?)"
        await self.conn.execute_query(update, (counter_name, next_id + nb))
        return [next_id + i for i in range(nb)]

    async def get_new_property_group_ids(self, nb: int):
        async with self.property_group_id_lock:
            return await self._get_id_counter_helper('property_group', nb)
