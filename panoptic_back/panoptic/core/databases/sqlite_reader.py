import sqlite3
import msgspec
from pathlib import Path
from typing import List, Type, TypeVar

# Generic type for msgspec Structs
T = TypeVar("T", bound=msgspec.Struct)

class SQLiteReader:
    def __init__(self, path: str | Path, timeout: int = 30000):
        self.db_path = Path(path)
        self.timeout = timeout
        self.conn = None
        self.is_loaded = False

    def start(self):
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found at {self.db_path}")

        self.conn = sqlite3.connect(
            f"file:{self.db_path}?mode=ro",
            uri=True,
            timeout=self.timeout,
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        # Bypassing Row factory is faster for msgspec positional mapping
        self.conn.row_factory = None
        self.conn.execute('PRAGMA query_only = ON;')
        self.is_loaded = True

    def close(self):
        if self.conn:
            self.conn.close()
            self.is_loaded = False

    def fetch_structs(self, sql: str, struct_type: Type[T]) -> List[T]:
        """Fetches rows and converts them directly to msgspec Structs."""
        if not self.is_loaded: self.start()
        cursor = self.conn.execute(sql)
        # positional mapping via array_like=True makes this incredibly fast
        return [msgspec.convert(row, type=struct_type) for row in cursor]

    def fetch_all(self, sql: str) -> List[tuple]:
        """Raw fetch for non-struct queries."""
        if not self.is_loaded: self.start()
        return self.conn.execute(sql).fetchall()