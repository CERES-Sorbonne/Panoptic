import json
import os
import sqlite3
from json import JSONDecodeError

import numpy as np

ALL_TABLES = ['images', 'images_properties', 'properties', 'parameters', 'tags']

sqlite3.register_adapter(np.array, lambda arr: arr.tobytes())
sqlite3.register_converter("array", np.frombuffer)

conn = sqlite3.connect("panoptic.db", detect_types=sqlite3.PARSE_DECLTYPES)


def create_tables_if_db_empty():
    query = "SELECT name FROM sqlite_master WHERE type='table'"
    cursor = execute_query(query)
    all_tables = cursor.fetchall()
    if len(all_tables) < len(ALL_TABLES):
        with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'scripts', 'create_db.sql'), 'r') as f:
            sql_script = f.read()
            cursor = conn.cursor()
            cursor.executescript(sql_script)
            conn.commit()


# Fonction utilitaire pour exécuter une requête SQL et commettre les modifications
def execute_query(query: str, parameters: tuple = None):
    cursor = conn.cursor()
    if parameters:
        cursor.execute(query, parameters)
    else:
        cursor.execute(query)
    conn.commit()
    return cursor


def decode_if_json(value):
    try:
        return json.loads(value)
    except (TypeError, JSONDecodeError):
        return value