from __future__ import annotations

import json
import os
import sqlite3
import sys
from json import JSONDecodeError

import aiosqlite
import numpy as np

from panoptic.compute import reload_tree

ALL_TABLES = ['images', 'property_values', 'properties', 'tags', 'folders', 'tabs']

aiosqlite.register_adapter(np.array, lambda arr: arr.tobytes())
aiosqlite.register_converter("array", lambda arr: np.frombuffer(arr, dtype='float32'))

conn: aiosqlite.Connection | None = None

loaded_path = None


# async def init():
#     print('init')
#     global conn
#     conn = await aiosqlite.connect(os.path.join(os.environ['PANOPTIC_DATA'], "panoptic.db"),
#                                    detect_types=sqlite3.PARSE_DECLTYPES)
#     await create_tables_if_db_empty()


async def load_project(path: str):
    print('load project', path)
    global conn
    global loaded_path
    conn = await aiosqlite.connect(os.path.join(path, "panoptic.db"),
                                   detect_types=sqlite3.PARSE_DECLTYPES)
    loaded_path = path
    await create_tables_if_db_empty()
    reload_tree(path)


async def close():
    global conn
    global loaded_path

    await conn.close()
    loaded_path = None


def is_loaded():
    return loaded_path is not None


async def create_tables_if_db_empty():
    query = "SELECT name FROM sqlite_master WHERE type='table'"
    cursor = await execute_query(query)
    all_tables = await cursor.fetchall()
    if len(list(all_tables)) < len(ALL_TABLES):
        if getattr(sys, 'frozen', False):
            # Le programme est exécuté en mode fichier unique
            BASE_PATH = sys._MEIPASS
        else:
            # Le programme est exécuté en mode script
            BASE_PATH = os.path.join('..', os.path.dirname(__file__))
        with open(os.path.join(BASE_PATH, '../scripts', 'create_db.sql'), 'r') as f:
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
