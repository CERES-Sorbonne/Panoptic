import json
import sqlite3
import types

import msgspec
from pathlib import Path
from typing import List, Type, TypeVar, Any, Iterable, Union

# Generic type for msgspec Structs
T = TypeVar("T", bound=msgspec.Struct)

def _is_json_field(t) -> bool:
    if t is Any or t == 'Any':
        return True
    if getattr(t, '__origin__', None) is list:
        return True
    # Unwrap Optional / Union and check each arg
    origin = getattr(t, '__origin__', None)
    if origin is Union or isinstance(t, types.UnionType):
        return any(_is_json_field(arg) for arg in t.__args__)
    return False

class SQLiteReader:
    def __init__(self, path: str | Path, timeout: int = 30000):
        self.db_path = Path(path)
        self.timeout = timeout
        self.conn: sqlite3.Connection | None = None
        self.is_loaded = False

    def start(self):
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found at {self.db_path}")

        self.conn = sqlite3.connect(
            str(self.db_path),
            timeout=self.timeout,
            detect_types=sqlite3.PARSE_DECLTYPES,
            check_same_thread=False,
        )

        # row_factory = None ensures rows are returned as tuples,
        # which is the fastest format for msgspec.convert.
        self.conn.row_factory = None

        # query_only prevents accidental writes; checkpoint still works.
        self.conn.execute('PRAGMA query_only = ON;')
        self.conn.execute("PRAGMA cache_size = -100000")  # 100MB cache
        self.conn.execute("PRAGMA temp_store = MEMORY")
        self.conn.execute("PRAGMA mmap_size = 30000000000")  # Enable mmap for speed if DB is large
        self.is_loaded = True

    def close(self):
        if self.conn:
            self.conn.execute('PRAGMA query_only = OFF;')
            self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            self.conn.close()
            self.is_loaded = False

    def fetch_structs(self, sql: str, struct_type: Type[T], params: Iterable[Any] = ()) -> List[T]:
        if not self.is_loaded:
            self.start()

        cursor = self.conn.execute(sql, params)
        cursor.row_factory = None

        fields = msgspec.structs.fields(struct_type)
        json_indices = [
            i for i, f in enumerate(fields)
            if _is_json_field(f.type)
        ]

        if not json_indices:
            return [msgspec.convert(row, type=struct_type) for row in cursor]

        results = []
        for row in cursor:
            row = list(row)
            for i in json_indices:
                if isinstance(row[i], str):
                    row[i] = json.loads(row[i])
            results.append(msgspec.convert(tuple(row), type=struct_type))
        return results

    def fetch_all(self, sql: str, params: Iterable[Any] = ()) -> List[tuple]:
        """Raw fetch for scalar values, counts, or manual queries."""
        if not self.is_loaded:
            self.start()
        return self.conn.execute(sql, params).fetchall()


    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()