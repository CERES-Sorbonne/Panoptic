import sqlite3
import time
import random
import uuid
from pathlib import Path

DB_PATH = Path("benchmark_disk.db")


def setup_db():
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(str(DB_PATH))
    # Optimize for file-based performance
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")

    conn.execute("CREATE TABLE benchmark_data (id TEXT PRIMARY KEY, val TEXT)")

    print("Generating 1,000,000 rows on disk...")
    # Insert in batches to be efficient
    data = []
    all_ids = []
    for i in range(1000000):
        uid = str(uuid.uuid4())
        data.append((uid, f"value_{i}"))
        all_ids.append(uid)
        if len(data) >= 100000:
            conn.executemany("INSERT INTO benchmark_data VALUES (?, ?)", data)
            data = []

    conn.commit()
    return conn, all_ids


def benchmark_in_clause(conn, ids_to_query):
    start = time.perf_counter()
    chunk_size = 32_000
    results_count = 0
    for i in range(0, len(ids_to_query), chunk_size):
        chunk = ids_to_query[i:i + chunk_size]
        placeholders = ",".join(["?"] * len(chunk))
        cursor = conn.execute(f"SELECT COUNT(*) FROM benchmark_data WHERE id IN ({placeholders})", chunk)
        results_count += cursor.fetchone()[0]
    end = time.perf_counter()
    return end - start, results_count


def benchmark_individual_selects(conn, ids_to_query):
    start = time.perf_counter()
    results_count = 0
    for i in ids_to_query:
        cursor = conn.execute("SELECT 1 FROM benchmark_data WHERE id = ?", (i,))
        if cursor.fetchone():
            results_count += 1
    end = time.perf_counter()
    return end - start, results_count


def benchmark_temp_table(conn, ids_to_query):
    start = time.perf_counter()
    # Ensure the temp table is created in memory despite the main DB being on disk
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("CREATE TEMP TABLE _search_ids (id TEXT)")

    conn.executemany("INSERT INTO _search_ids VALUES (?)", [(i,) for i in ids_to_query])
    conn.execute("CREATE INDEX IF NOT EXISTS idx_temp_id ON _search_ids(id)")

    cursor = conn.execute("""
        SELECT COUNT(*) FROM benchmark_data 
        WHERE id IN (SELECT id FROM _search_ids)
    """)
    results_count = cursor.fetchone()[0]

    conn.execute("DROP TABLE _search_ids")
    end = time.perf_counter()
    return end - start, results_count


def run_benchmarks():
    conn, all_ids = setup_db()
    ids_to_query = random.sample(all_ids, 100000)

    print(f"\nDisk Benchmark (1M rows, 100k queries):")
    print("-" * 50)

    # 1. Temp Table Join
    t_temp, count_temp = benchmark_temp_table(conn, ids_to_query)
    print(f"Temp Table Join:   {t_temp:.4f}s")

    # 2. Chunked IN Clause
    t_in, count_in = benchmark_in_clause(conn, ids_to_query)
    print(f"Chunked IN Clause: {t_in:.4f}s")

    # 3. Individual Selects
    t_ind, count_ind = benchmark_individual_selects(conn, ids_to_query)
    print(f"Individual Selects: {t_ind:.4f}s")

    conn.close()
    if DB_PATH.exists():
        DB_PATH.unlink()


if __name__ == "__main__":
    run_benchmarks()