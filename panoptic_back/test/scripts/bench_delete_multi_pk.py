import sqlite3
import time
import random
import uuid
from pathlib import Path

DB_PATH = Path("benchmark_production.db")
OP_DELETE = "remove"
TOTAL_ROWS = 1_000_000
DELETE_COUNT = 100_000


def setup_db():
    """Real-world SSD setup: WAL mode, Sync Normal, Physical File."""
    if DB_PATH.exists():
        try:
            DB_PATH.unlink()
            for suffix in ["-wal", "-shm"]:
                p = Path(str(DB_PATH) + suffix)
                if p.exists(): p.unlink()
        except PermissionError:
            pass  # Handle cases where file is still locked

    conn = sqlite3.connect(str(DB_PATH))

    # Production Grade Settings
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA cache_size = -100000")  # 100MB cache

    conn.execute("CREATE TABLE data (id TEXT PRIMARY KEY, val TEXT, commit_id INT)")
    conn.execute("CREATE TABLE data_history (id TEXT, val TEXT, commit_id INT, op_type TEXT)")

    data = [(str(uuid.uuid4()), f"val_{i}", 1) for i in range(TOTAL_ROWS)]
    conn.executemany("INSERT INTO data VALUES (?, ?, ?)", data)
    conn.commit()

    ids = [row[0] for row in data]
    return conn, ids


def bench_executemany(ids_to_del):
    conn = sqlite3.connect(str(DB_PATH))
    id_params = [(i,) for i in ids_to_del]

    start = time.perf_counter()
    conn.execute("BEGIN")

    # Move to history
    conn.executemany(f"""
        INSERT INTO data_history (id, val, commit_id, op_type)
        SELECT id, val, 2, '{OP_DELETE}' FROM data WHERE id = ?
    """, id_params)

    # Delete from live
    conn.executemany("DELETE FROM data WHERE id = ?", id_params)

    conn.commit()
    duration = time.perf_counter() - start
    conn.close()
    return duration


def bench_temp_table(ids_to_del):
    conn = sqlite3.connect(str(DB_PATH))

    start = time.perf_counter()
    conn.execute("BEGIN")
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("CREATE TEMP TABLE _staging (id TEXT)")

    # Upload IDs once
    conn.executemany("INSERT INTO _staging VALUES (?)", [(i,) for i in ids_to_del])
    conn.execute("CREATE INDEX idx_stg ON _staging(id)")

    # Set-based Move
    conn.execute(f"""
        INSERT INTO data_history (id, val, commit_id, op_type)
        SELECT d.id, d.val, 2, '{OP_DELETE}' FROM data d
        JOIN _staging s ON d.id = s.id
    """)

    # Set-based Delete
    conn.execute("DELETE FROM data WHERE id IN (SELECT id FROM _staging)")

    conn.commit()
    duration = time.perf_counter() - start
    conn.close()
    return duration


# --- Running the Tests ---
print(f"--- Starting SSD Benchmark: {DELETE_COUNT} rows from {TOTAL_ROWS} ---")

print("Test 1: Executemany...")
_, all_ids = setup_db()
target_ids = random.sample(all_ids, DELETE_COUNT)
t_many = bench_executemany(target_ids)
print(f"✅ Completed in {t_many:.4f}s")

print("\nTest 2: Temp Table...")
_, all_ids = setup_db()
target_ids = random.sample(all_ids, DELETE_COUNT)
t_tmp = bench_temp_table(target_ids)
print(f"✅ Completed in {t_tmp:.4f}s")

print("\n--- Final Result ---")
if t_tmp < t_many:
    print(f"🏆 Temp Table is {t_many / t_tmp:.2f}x faster than Executemany")
else:
    print(f"🏆 Executemany is {t_tmp / t_many:.2f}x faster (likely due to SSD caching/latency)")