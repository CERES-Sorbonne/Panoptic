import logging
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from panoptic.core.databases.db_description import DbDescription


class SQLiteWriter:
    VERSION_TABLE = "_version"
    VERSION_KEY = "db_version"

    def __init__(self, path: str | Path, description: DbDescription, timeout: int = 30000):
        self.db_path = Path(path)
        self.desc = description
        self.timeout = timeout

        # isolation_level=None is required for manual BEGIN IMMEDIATE transactions
        self.conn = sqlite3.connect(
            str(self.db_path),
            timeout=self.timeout,
            isolation_level=None,
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        self.is_loaded = False

        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA synchronous = NORMAL")
        self.conn.execute("PRAGMA temp_store = MEMORY")

    def start(self):
        """
        Initializes the database: pragmas, versioning, recursive migrations,
        and missing table creation.
        """
        # Ensure the directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # 1. Configure Concurrency & Safety
        self.conn.execute('PRAGMA journal_mode=WAL;')
        self.conn.execute('PRAGMA synchronous=NORMAL;')
        self.conn.execute('PRAGMA foreign_keys=1;')

        # 2. Setup Versioning & Handle Migrations
        self._ensure_version_table()
        self._handle_migrations()

        # 3. Create missing tables defined in the description
        for table_name, create_query in self.desc.tables.items():
            if not self._table_exists(table_name):
                # Using executescript for initial table creation
                self.conn.executescript(create_query)

        self.is_loaded = True
        logging.debug(f"Database {self.db_path.name} started successfully.")

    def close(self):
        """Manually closes the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
            self.is_loaded = False
            logging.debug("Database connection closed.")

    def __del__(self):
        """Safety hook for garbage collection."""
        try:
            self.close()
        except Exception:
            pass

    def _handle_migrations(self):
        """
        Recursive migration loop. Increments version one by one
        using provided migration scripts.
        """
        while True:
            current_v = self._get_db_version()
            target_v = self.desc.version

            if current_v >= target_v:
                break

            if current_v in self.desc.migrations:
                logging.info(f"Migrating {self.db_path.name} from v{current_v} to v{current_v + 1}...")

                migration_func = self.desc.migrations[current_v]
                try:
                    # Run the migration function
                    migration_func(self)

                    # Increment version immediately after successful migration step
                    new_v = current_v + 1
                    self._set_db_version(new_v)
                except Exception as e:
                    logging.error(f"Migration failed at version {current_v}: {e}")
                    raise e
            else:
                logging.warning(f"No migration path found for {self.db_path.name} v{current_v}. Update stopped.")
                break

    def _ensure_version_table(self):
        """Internal setup for the version tracking table."""
        self.conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.VERSION_TABLE} (
                key TEXT PRIMARY KEY NOT NULL,
                value INTEGER NOT NULL
            );
        """)
        self.conn.execute(
            f"INSERT OR IGNORE INTO {self.VERSION_TABLE} (key, value) VALUES (?, 1)",
            (self.VERSION_KEY,)
        )

    def _get_db_version(self) -> int:
        cursor = self.conn.execute(
            f"SELECT value FROM {self.VERSION_TABLE} WHERE key = ?", (self.VERSION_KEY,)
        )
        return cursor.fetchone()[0]

    def _set_db_version(self, version: int):
        self.conn.execute(
            f"UPDATE {self.VERSION_TABLE} SET value = ? WHERE key = ?",
            (version, self.VERSION_KEY)
        )

    @contextmanager
    def transaction(self):
        """
        Locks the database for writing via BEGIN IMMEDIATE.
        Ensures atomicity and prevents Deadlocks in WAL mode.
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("BEGIN IMMEDIATE")
            yield cursor
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            logging.error(f"Transaction rolled back: {e}")
            raise e
        finally:
            cursor.close()

    def _validate_query(self, query: str):
        """Enforces write operations to stay within a transaction block."""
        is_write = re.match(r'^\s*(INSERT|UPDATE|DELETE|REPLACE|DROP|ALTER)', query, re.IGNORECASE)
        if is_write and not self.conn.in_transaction:
            raise RuntimeError(
                f"Forbidden: Write operation attempted outside of a transaction: {query[:50]}..."
            )

    def execute_query(self, query: str, parameters: tuple = None):
        """Executes a single query. Restricts writes to transaction blocks."""
        self._validate_query(query)
        cursor = self.conn.cursor()
        if parameters:
            cursor.execute(query, parameters)
        else:
            cursor.execute(query)

        if not self.conn.in_transaction:
            self.conn.commit()
        return cursor

    def execute_query_many(self, query: str, data: list):
        """Executes batch operations. Strictly requires a transaction for writes."""
        self._validate_query(query)
        cursor = self.conn.cursor()
        cursor.executemany(query, data)
        if not self.conn.in_transaction:
            self.conn.commit()
        return cursor

    def _table_exists(self, table_name: str) -> bool:
        query = "SELECT name FROM sqlite_master WHERE type='table' AND name=?"
        return self.conn.execute(query, (table_name,)).fetchone() is not None