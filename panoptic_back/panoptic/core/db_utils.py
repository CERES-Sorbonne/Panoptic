import json
import os
import sqlite3
from json import JSONDecodeError

import aiosqlite
import numpy as np

ALL_TABLES = ['images', 'images_properties', 'properties', 'tags', 'folders', 'tabs']

aiosqlite.register_adapter(np.array, lambda arr: arr.tobytes())
aiosqlite.register_converter("array", np.frombuffer)

conn: aiosqlite.Connection | None = None


async def init():
    global conn
    conn = await aiosqlite.connect("panoptic.db", detect_types=sqlite3.PARSE_DECLTYPES)
    await create_tables_if_db_empty()


async def create_tables_if_db_empty():
    query = "SELECT name FROM sqlite_master WHERE type='table'"
    cursor = await execute_query(query)
    all_tables = await cursor.fetchall()
    if len(list(all_tables)) < len(ALL_TABLES):
        with open(os.path.join(os.path.dirname(__file__), '../scripts', 'create_db.sql'), 'r') as f:
            sql_script = f.read()
            async with conn.executescript(sql_script) as cursor:
                await conn.commit()


# Fonction utilitaire pour exécuter une requête SQL et commettre les modifications
async def execute_query(query: str, parameters: tuple = None):
    cursor = await conn.cursor()
    if parameters:
        await cursor.execute(query, parameters)
    else:
        await cursor.execute(query)
    await conn.commit()
    return cursor


def decode_if_json(value):
    try:
        return json.loads(value)
    except (TypeError, JSONDecodeError, UnicodeDecodeError):
        return value
