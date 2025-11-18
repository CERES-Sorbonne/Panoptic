import asyncio
import logging
import os
import sqlite3
from pathlib import Path

import aiosqlite

from panoptic.core.panoptic_db.create import panoptic_tables, DB_VERSION, panoptic_db_version

DB_LOCK = asyncio.Lock()


def panoptic_db_lock(func):
    async def wrapper(*args, **kwargs):
        async with DB_LOCK:
            return await func(*args, **kwargs)

    return wrapper


class DbConnection:
    def __init__(self, path: Path):
        self.db_path = path
        self.is_loaded = False
        self.conn: aiosqlite.Connection | None = None

    async def start(self):
        """
        Startup function should be called first
        Cannot be done in __init__ because of async
        """
        # create connection
        if not self.db_path.parent.exists():
            print('Create folder for panoptic db')
            os.makedirs(self.db_path.parent)
        self.conn = await aiosqlite.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        # use foreign_keys checks
        async with self.conn.executescript('PRAGMA foreign_keys = 1') as cursor:
            await self.conn.commit()

        # check if the db is empty or has missing tables
        for table_name, create_query in panoptic_tables.items():
            # Check if the table exists
            if not await self._table_exists(table_name):
                # If not, create the table
                async with self.conn.executescript(create_query) as cursor:
                    await self.conn.commit()
                print(f"Table '{table_name}' created.")

        # check if db version is the same as the software version
        db_version = await self.get_param(DB_VERSION)
        if int(db_version) != panoptic_db_version:
            logging.warning(f'Panoptic DB Version ({db_version}) doesnt match Panoptic Software DB Version ({panoptic_db_version})')
            await self.update_version(int(db_version), panoptic_db_version)
        self.is_loaded = True

    async def close(self):
        await self.conn.close()

    async def update_version(self, db_version: int, target_version: int):
        # No migration for now
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
