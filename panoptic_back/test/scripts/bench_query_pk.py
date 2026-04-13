import sqlite3
import time
import msgspec
from typing import List, Tuple


# 1. Setup Data Structures
class Sha1Value(msgspec.Struct):
    property_id: int
    sha1: str
    value: float


def setup_db(conn: sqlite3.Connection, count: int):
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = OFF")
    conn.execute(
        "CREATE TABLE sha1_values (property_id INTEGER, sha1 TEXT, value REAL, PRIMARY KEY(property_id, sha1))")

    # Generate 1M rows
    print(f"Generating {count} rows...")
    data = [(i, f"sha1_{i}", float(i)) for i in range(count)]
    conn.executemany("INSERT INTO sha1_values VALUES (?, ?, ?)", data)
    conn.commit()
    return data


# 2. Method A: Chunked IN Clause
def chunked_in(conn: sqlite3.Connection, pks: List[Tuple[int, str]], chunk_size: int = 500):
    results = []
    # SQLite has a limit on variables (SQLITE_MAX_VARIABLE_NUMBER)
    # For composite IN (a, b), each row uses 2 variables.
    for i in range(0, len(pks), chunk_size):
        chunk = pks[i: i + chunk_size]
        # Generate placeholders: (VALUES (?,?), (?,?), ...)
        placeholders = ", ".join(["(?,?)"] * len(chunk))
        flattened_pks = [item for sublist in chunk for item in sublist]

        sql = f"SELECT * FROM sha1_values WHERE (property_id, sha1) IN (VALUES {placeholders})"
        cur = conn.execute(sql, flattened_pks)
        results.extend(cur.fetchall())
    return results


# 3. Method B: Temp Table Join
def temp_table_join(conn: sqlite3.Connection, pks: List[Tuple[int, str]]):
    conn.execute("CREATE TEMP TABLE IF NOT EXISTS tmp_pks (pid INTEGER, s1 TEXT)")

    # Bulk insert into temp table
    conn.executemany("INSERT INTO tmp_pks VALUES (?, ?)", pks)

    # Join
    sql = """
        SELECT t.* FROM sha1_values t
        INNER JOIN tmp_pks tmp ON t.property_id = tmp.pid AND t.sha1 = tmp.s1
    """
    results = conn.execute(sql).fetchall()

    # Cleanup
    conn.execute("DELETE FROM tmp_pks")
    return results


# 4. Execution
if __name__ == "__main__":
    db = sqlite3.connect("test1.db")
    row_count = 1_000_000
    all_data = setup_db(db, row_count)

    # We want to look up all 1M rows
    search_pks = [(d[0], d[1]) for d in all_data]

    print(f"\n--- Starting Benchmark (1M Rows) ---")

    # Benchmark Temp Table
    start = time.perf_counter()
    res_b = temp_table_join(db, search_pks)
    end_b = time.perf_counter()
    print(f"Temp Table + Join: {end_b - start:.4f}s (Rows found: {len(res_b)})")

    # Benchmark Chunked IN
    # Note: We use a larger chunk size to give 'IN' a fighting chance
    start = time.perf_counter()
    res_a = chunked_in(db, search_pks, chunk_size=900)
    end_a = time.perf_counter()
    print(f"Chunked IN Clause: {end_a - start:.4f}s (Rows found: {len(res_a)})")