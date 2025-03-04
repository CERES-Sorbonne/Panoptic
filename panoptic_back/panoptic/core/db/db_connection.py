import asyncio
import logging
import os
import sqlite3

import aiosqlite
import numpy as np

from panoptic.core.db.create import tables, DB_VERSION, software_db_version
from panoptic.core.db.migrations.v3 import v3_sql
from panoptic.core.db.migrations.v4 import v4_sql
from panoptic.core.db.migrations.v5 import v5_sql
from panoptic.core.db.migrations.v6 import v6_sql

aiosqlite.register_adapter(np.array, lambda arr: arr.tobytes())
aiosqlite.register_converter("array", lambda arr: np.frombuffer(arr, dtype='float32'))

DB_LOCK = asyncio.Lock()


def db_lock(func):
    async def wrapper(*args, **kwargs):
        async with DB_LOCK:
            return await func(*args, **kwargs)

    return wrapper


class DbConnection:
    def __init__(self, path):
        self.folder_path = path
        self.db_path = os.path.join(path, "panoptic.db")
        self.is_loaded = False
        self.conn: aiosqlite.Connection | None = None

    async def start(self):
        """
        Startup function should be called first
        Cannot be done in __init__ because of async
        """
        # create connection
        self.conn = await aiosqlite.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        # use foreign_keys checks
        async with self.conn.executescript('PRAGMA foreign_keys = 1') as cursor:
            await self.conn.commit()

        # check if the db is empty or has missing tables
        for table_name, create_query in tables.items():
            # Check if the table exists
            if not await self._table_exists(table_name):
                # If not, create the table
                async with self.conn.executescript(create_query) as cursor:
                    await self.conn.commit()
                print(f"Table '{table_name}' created.")

        # check if db version is the same as the software version
        db_version = await self.get_param(DB_VERSION)
        if int(db_version) != software_db_version:
            logging.warning(f'DB Version ({db_version}) doesnt match Software DB Version ({software_db_version})')
            await self.update_version(int(db_version), software_db_version)
        self.is_loaded = True

    async def update_version(self, db_version: int, target_version: int):
        if db_version < 3:
            await self.conn.executescript(v3_sql)
        if db_version < 4:
            await self.conn.executescript(v4_sql)
        if db_version < 5:
            await self.conn.executescript(v5_sql)
        if db_version < 6:
            await self.conn.executescript(v6_sql)

        await self.set_param(DB_VERSION, str(target_version))
        logging.warning(f'Correctly updated to Software DB Version ({target_version})')

    async def execute_query(self, query: str, parameters: tuple = None):
        cursor = await self.conn.cursor()
        if parameters:
            await cursor.execute(query, parameters)
        else:
            await cursor.execute(query)
        await self.conn.commit()
        return cursor

    async def execute_query_many(self, query, data: list):
        cursor = await self.conn.cursor()
        await cursor.executemany(query, data)
        await self.conn.commit()
        return cursor

    async def _table_exists(self, table_name: str):
        # Use the sqlite_master table to check if the table exists
        query = f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'"
        cursor = await self.execute_query(query)
        result = await cursor.fetchone()

        return result is not None

    async def get_param(self, key: str) -> str | None:
        query = f'SELECT value FROM panoptic WHERE key="{key}";'
        cursor = await self.execute_query(query)
        row = await cursor.fetchone()
        if row:
            return row[0]
        return None

    async def set_param(self, key: str, value: str):
        query = f"""
                INSERT OR REPLACE INTO panoptic (key, value)
                VALUES ('{key}', '{value}');
        """
        cursor = await self.execute_query(query)
        return cursor
