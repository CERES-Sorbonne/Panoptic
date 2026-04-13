import sqlite3
import os

def run_concurrency_test():
    db_file = 'concurrency_test.db'
    if os.path.exists(db_file):
        os.remove(db_file)

    # 1. Setup the database and WAL mode
    setup_conn = sqlite3.connect(db_file)
    setup_conn.execute("PRAGMA journal_mode=WAL;")
    setup_conn.execute("CREATE TABLE test_data (id INTEGER PRIMARY KEY, value TEXT);")
    setup_conn.close()

    # 2. Connection A: The Writer
    conn_a = sqlite3.connect(db_file)
    # 3. Connection B: The Outside Observer
    conn_b = sqlite3.connect(db_file)

    try:
        # Start transaction on A
        conn_a.execute("BEGIN TRANSACTION;")

        print("Connection A: Writing 1,000 rows...")
        data = [(i, f"Value {i}") for i in range(1, 1001)]
        conn_a.executemany("INSERT INTO test_data (id, value) VALUES (?, ?);", data)

        # Connection A checks its own work
        count_a = conn_a.execute("SELECT COUNT(*) FROM test_data;").fetchone()[0]
        print(f"Connection A (Inside Transaction): I see {count_a} rows.")

        # Connection B tries to read the same table
        count_b = conn_b.execute("SELECT COUNT(*) FROM test_data;").fetchone()[0]
        print(f"Connection B (Outside Transaction): I see {count_b} rows.")

        print("---")
        print("Observation: Connection B is NOT blocked, but it cannot see A's uncommitted data.")

        # Finalize
        conn_a.commit()
        print("---")
        print("Connection A: Committed.")

        # Now Connection B checks again
        count_b_after = conn_b.execute("SELECT COUNT(*) FROM test_data;").fetchone()[0]
        print(f"Connection B (Post-Commit): Now I see {count_b_after} rows.")

    finally:
        conn_a.close()
        conn_b.close()
        if os.path.exists(db_file):
            os.remove(db_file)

if __name__ == "__main__":
    run_concurrency_test()