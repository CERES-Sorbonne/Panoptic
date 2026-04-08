import sqlite3
import time
import os
from dataclasses import dataclass
import msgspec
import adbc_driver_sqlite.dbapi as arrow_sqlite
import apsw

DB_NAME = "benchmark.db"
COUNT = 1_000_000


@dataclass
class FileDataclass:
    id: int
    name: str
    size: int
    is_active: bool


class FileStruct(msgspec.Struct, array_like=True):
    id: int
    name: str
    size: int
    is_active: int


def setup_db():
    if os.path.exists(DB_NAME): os.remove(DB_NAME)
    conn = sqlite3.connect(DB_NAME)
    conn.execute("CREATE TABLE files (id INTEGER, name TEXT, size INTEGER, is_active BOOLEAN)")
    data = [(i, f"file_SdfsdF DS_F SD_F-sdf sdf sdf sdfsdazezatr azdfsth ze  redsqfsrgt esf_{i}.txt", i * 10, i % 2 == 0) for i in range(COUNT)]
    conn.executemany("INSERT INTO files VALUES (?, ?, ?, ?)", data)
    conn.commit()
    conn.close()


def collect_ids_pure_python(items, id_getter) -> float:
    """
    Pure Python loop accumulation — no sum(), no list comp, no C shortcut.
    Returns elapsed time. id_getter is a callable that extracts .id from one item.
    """
    start = time.perf_counter()
    total = 0
    for item in items:
        total += id_getter(item)
    end = time.perf_counter()
    return end - start


# --- sqlite3 ---

def bench_dataclass():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    t_fetch = time.perf_counter()
    rows = conn.execute("SELECT * FROM files").fetchall()
    result = [FileDataclass(**row) for row in rows]
    t_fetch = time.perf_counter() - t_fetch
    conn.close()
    t_ids = collect_ids_pure_python(result, lambda r: r.id)
    return t_fetch, t_ids


def bench_pure_row():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    t_fetch = time.perf_counter()
    result = conn.execute("SELECT * FROM files").fetchall()
    t_fetch = time.perf_counter() - t_fetch
    conn.close()
    t_ids = collect_ids_pure_python(result, lambda r: r["id"])
    return t_fetch, t_ids


def bench_msgspec():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = None
    t_fetch = time.perf_counter()
    cursor = conn.execute("SELECT * FROM files")
    result = [msgspec.convert(row, type=FileStruct) for row in cursor]
    t_fetch = time.perf_counter() - t_fetch
    conn.close()
    t_ids = collect_ids_pure_python(result, lambda r: r.id)
    return t_fetch, t_ids


# --- Arrow ---

def bench_arrow_adbc():
    t_fetch = time.perf_counter()
    with arrow_sqlite.connect(f"file:{DB_NAME}") as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM files")
            table = cur.fetch_arrow_table()
    t_fetch = time.perf_counter() - t_fetch
    # Arrow column → Python list first, then pure loop (no C Arrow compute)
    ids = table.column("id").to_pylist()
    t_ids = time.perf_counter()
    total = 0
    for i in ids:
        total += i
    t_ids = time.perf_counter() - t_ids
    return t_fetch, t_ids


# --- apsw ---

def bench_apsw_raw():
    conn = apsw.Connection(DB_NAME)
    t_fetch = time.perf_counter()
    result = conn.execute("SELECT * FROM files").fetchall()
    t_fetch = time.perf_counter() - t_fetch
    conn.close()
    # raw tuples: id is index 0
    t_ids = collect_ids_pure_python(result, lambda r: r[0])
    return t_fetch, t_ids


def bench_apsw_msgspec():
    conn = apsw.Connection(DB_NAME)
    t_fetch = time.perf_counter()
    cursor = conn.execute("SELECT * FROM files")
    result = [msgspec.convert(row, type=FileStruct) for row in cursor]
    t_fetch = time.perf_counter() - t_fetch
    conn.close()
    t_ids = collect_ids_pure_python(result, lambda r: r.id)
    return t_fetch, t_ids


def bench_apsw_fetchall_msgspec():
    conn = apsw.Connection(DB_NAME)
    t_fetch = time.perf_counter()
    rows = conn.execute("SELECT * FROM files").fetchall()
    result = [msgspec.convert(row, type=FileStruct) for row in rows]
    t_fetch = time.perf_counter() - t_fetch
    conn.close()
    t_ids = collect_ids_pure_python(result, lambda r: r.id)
    return t_fetch, t_ids


# --- Runner ---

if __name__ == "__main__":
    print("Generating 1,000,000 rows...")
    setup_db()

    RUNS = 3

    def avg(fn):
        fetch_times, id_times = [], []
        for _ in range(RUNS):
            t_fetch, t_ids = fn()
            fetch_times.append(t_fetch)
            id_times.append(t_ids)
        return sum(fetch_times) / RUNS, sum(id_times) / RUNS

    benchmarks = [
        ("Arrow (ADBC)",             bench_arrow_adbc),
        ("sqlite3  raw row",         bench_pure_row),
        ("sqlite3  + msgspec",       bench_msgspec),
        ("sqlite3  dataclass",       bench_dataclass),
        ("apsw     raw row",         bench_apsw_raw),
        ("apsw     + msgspec iter",  bench_apsw_msgspec),
        ("apsw     + msgspec batch", bench_apsw_fetchall_msgspec),
    ]

    print(f"\n{'Method':<28} | {'Fetch (s)':<10} | {'ID loop (s)':<12} | {'Total (s)'}")
    print("-" * 68)
    for label, fn in benchmarks:
        t_f, t_i = avg(fn)
        print(f"{label:<28} | {t_f:<10.4f} | {t_i:<12.4f} | {t_f + t_i:.4f}")