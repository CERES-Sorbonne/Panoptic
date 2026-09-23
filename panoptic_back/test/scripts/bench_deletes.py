import sqlite3
import time
import random
import uuid
from pathlib import Path

DB_PATH = Path("benchmark_history.db")
OP_DELETE = "remove"


def setup_db():
    if DB_PATH.exists(): DB_PATH.unlink()
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")

    conn.execute("CREATE TABLE data (id TEXT PRIMARY KEY, val TEXT, commit_id INT)")
    conn.execute("CREATE TABLE data_history (id TEXT, val TEXT, commit_id INT, op_type TEXT)")

    print("Populating 1,000,000 rows...")
    data = [(str(uuid.uuid4()), f"val_{i}", 1) for i in range(1000000)]
    conn.executemany("INSERT INTO data VALUES (?, ?, ?)", data)
    conn.commit()
    return conn, [row[0] for row in data]


def bench_history_chunked_in(ids):
    conn = sqlite3.connect(str(DB_PATH))
    ids_to_del = random.sample(ids, 100000)
    chunk_size = 32_000

    start = time.perf_counter()
    conn.execute("BEGIN")
    for i in range(0, len(ids_to_del), chunk_size):
        chunk = ids_to_del[i:i + chunk_size]
        placeholders = ",".join(["?"] * len(chunk))

        # 1. Insert into history
        conn.execute(f"""
            INSERT INTO data_history (id, val, commit_id, op_type)
            SELECT id, val, 2, '{OP_DELETE}' FROM data 
            WHERE id IN ({placeholders})
        """, chunk)

        # 2. Delete from live
        conn.execute(f"DELETE FROM data WHERE id IN ({placeholders})", chunk)

    conn.commit()
    duration = time.perf_counter() - start
    conn.close()
    return duration


def bench_history_temp_table(ids):
    conn = sqlite3.connect(str(DB_PATH))
    ids_to_del = random.sample(ids, 100000)

    start = time.perf_counter()
    conn.execute("BEGIN")
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("CREATE TEMP TABLE _staging (id TEXT)")

    # Send IDs to DB once
    conn.executemany("INSERT INTO _staging VALUES (?)", [(i,) for i in ids_to_del])
    conn.execute("CREATE INDEX idx_stg ON _staging(id)")  # Optimize the join

    # 1. Insert into history via Join
    conn.execute(f"""
        INSERT INTO data_history (id, val, commit_id, op_type)
        SELECT d.id, d.val, 2, '{OP_DELETE}' FROM data d
        JOIN _staging s ON d.id = s.id
    """)

    # 2. Delete from live via Subquery
    conn.execute("DELETE FROM data WHERE id IN (SELECT id FROM _staging)")

    conn.commit()
    duration = time.perf_counter() - start
    conn.close()
    return duration


def bench_history_executemany(ids):
    conn = sqlite3.connect(str(DB_PATH))
    ids_to_del = random.sample(ids, 100000)
    # Reshape for executemany: list of tuples
    id_params = [(i,) for i in ids_to_del]

    start = time.perf_counter()
    conn.execute("BEGIN")

    # 1. Insert into history
    # Note: SQLite must run this SELECT for every single ID in the loop
    conn.executemany(f"""
        INSERT INTO data_history (id, val, commit_id, op_type)
        SELECT id, val, 2, '{OP_DELETE}' FROM data 
        WHERE id = ?
    """, id_params)

    # 2. Delete from live
    conn.executemany("DELETE FROM data WHERE id = ?", id_params)

    conn.commit()
    duration = time.perf_counter() - start
    conn.close()
    return duration


print("--- HISTORY + DELETE BENCHMARK (100k rows) ---")

_, ids = setup_db()
t_in = bench_history_chunked_in(ids)
print(f"Chunked IN (History+Delete): {t_in:.4f}s")

_, ids = setup_db()
t_tmp = bench_history_temp_table(ids)
print(f"Temp Table (History+Delete): {t_tmp:.4f}s")

_, ids = setup_db()
t_many = bench_history_executemany(ids)
print(f"Executemany:    {t_many:.4f}s")