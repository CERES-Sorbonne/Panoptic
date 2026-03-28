import sqlite3
import time
import os
from dataclasses import dataclass
import msgspec
import pyarrow as pa
import adbc_driver_sqlite.dbapi as arrow_sqlite

# 1. SETUP: Schema and Data Generation
DB_NAME = "benchmark.db"
COUNT = 1_000_000


@dataclass
class FileDataclass:
    id: int
    name: str
    size: int
    is_active: bool


class FileStruct(msgspec.Struct):
    id: int
    name: str
    size: int
    is_active: bool


def setup_db():
    if os.path.exists(DB_NAME): os.remove(DB_NAME)
    conn = sqlite3.connect(DB_NAME)
    conn.execute("CREATE TABLE files (id INTEGER, name TEXT, size INTEGER, is_active BOOLEAN)")
    data = [(i, f"file_SdfsdF DS_F SD_F-sdf sdf sdf sdfsdazezatr azdfsth ze  redsqfsrgt esf_{i}.txt", i * 10, i % 2 == 0) for i in range(COUNT)]
    conn.executemany("INSERT INTO files VALUES (?, ?, ?, ?)", data)
    conn.commit()
    conn.close()


# 2. BENCHMARK FUNCTIONS
def bench_dataclass():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    start = time.perf_counter()
    rows = conn.execute("SELECT * FROM files").fetchall()
    # High overhead: creating 1M python objects
    result = [FileDataclass(**row) for row in rows]
    end = time.perf_counter()
    conn.close()
    return end - start


def bench_pure_row():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    start = time.perf_counter()
    # Medium overhead: sqlite3.Row is faster than a dict but still row-based
    result = conn.execute("SELECT * FROM files").fetchall()
    end = time.perf_counter()
    conn.close()
    return end - start


class FileStruct(msgspec.Struct, array_like=True):
    id: int
    name: str
    size: int
    is_active: int  # Changed from bool to int to match SQLite 0/1


def bench_msgspec():
    conn = sqlite3.connect(DB_NAME)
    # Important: Do NOT use row_factory=sqlite3.Row here.
    # msgspec is fastest when it consumes raw tuples.
    conn.row_factory = None
    start = time.perf_counter()
    cursor = conn.execute("SELECT * FROM files")

    # This now maps positionally: tuple[0] -> id, tuple[1] -> name...
    result = [msgspec.convert(row, type=FileStruct) for row in cursor]

    end = time.perf_counter()
    conn.close()
    return end - start

def bench_arrow_adbc():
    # Zero-copy approach: using ADBC to pull directly into Arrow
    start = time.perf_counter()
    with arrow_sqlite.connect(f"file:{DB_NAME}") as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM files")
            table = cur.fetch_arrow_table()
    end = time.perf_counter()
    return end - start


# EXECUTION
if __name__ == "__main__":
    print("Generating 1,000,000 rows...")
    setup_db()

    print(f"{'Method':<20} | {'Time (s)':<10}")
    print("-" * 35)

    # We run Arrow first because it's the baseline for 'native' speed
    print(f"{'Apache Arrow (ADBC)':<20} | {bench_arrow_adbc():.4f}s")
    print(f"{'Pure sqlite3.Row':<20} | {bench_pure_row():.4f}s")
    print(f"{'msgspec.Struct':<20} | {bench_msgspec():.4f}s")
    print(f"{'Standard Dataclass':<20} | {bench_dataclass():.4f}s")