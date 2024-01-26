from __future__ import annotations

import json
import os
import sqlite3
from json import JSONDecodeError

import aiosqlite
import numpy as np

from panoptic.compute import reload_tree
from panoptic.core.db.create import tables

ALL_TABLES = ['images', 'property_values', 'properties', 'tags', 'folders', 'tabs']

aiosqlite.register_adapter(np.array, lambda arr: arr.tobytes())
aiosqlite.register_converter("array", lambda arr: np.frombuffer(arr, dtype='float32'))

conn: aiosqlite.Connection | None = None

loaded_path = None

software_db_version = 1


async def load_project(path: str):
    print('load project_id', path)
    global conn
    global loaded_path
    conn = await aiosqlite.connect(os.path.join(path, "panoptic.db"),
                                   detect_types=sqlite3.PARSE_DECLTYPES)
    loaded_path = path
    await create_missing_tables()
    db_version = await get_param('db_version')
    if db_version is None:
        await set_param('db_version', str(software_db_version))
    reload_tree(path)
    from panoptic.core import clear_import
    await clear_import()


async def close():
    global conn
    global loaded_path

    await conn.close()
    loaded_path = None


def is_loaded():
    return loaded_path is not None


async def create_missing_tables():
    for table_name, create_query in tables.items():
        # Check if the table exists
        if not await table_exists(table_name):
            # If not, create the table
            async with conn.executescript(create_query) as cursor:
                await conn.commit()
            print(f"Table '{table_name}' created.")


async def table_exists(table_name):
    # Use the sqlite_master table to check if the table exists
    query = f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'"
    cursor = await execute_query(query)
    result = await cursor.fetchone()

    return result is not None

async def get_param(key: str):
    query = f'SELECT value FROM panoptic WHERE key="{key}";'
    cursor = await execute_query(query)
    row = await cursor.fetchone()
    if row:
        return row[0]
    return None


async def set_param(key: str, value: str):
    query = f"""
            INSERT OR REPLACE INTO panoptic (key, value)
            VALUES ('{key}', '{value}');
    """
    cursor = await execute_query(query)
    return cursor



# Fonction utilitaire pour exécuter une requête SQL et commettre les modifications
async def execute_query(query: str, parameters: tuple = None):
    cursor = await conn.cursor()
    if parameters:
        await cursor.execute(query, parameters)
    else:
        await cursor.execute(query)
    await conn.commit()
    return cursor


async def execute_query_many(query, data: list):
    cursor = await conn.cursor()
    await cursor.executemany(query, data)
    await conn.commit()
    return cursor


def decode_if_json(value):
    try:
        return json.loads(value)
    except (TypeError, JSONDecodeError, UnicodeDecodeError):
        return value
