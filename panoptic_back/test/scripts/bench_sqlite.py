import sqlite3
import time
import random
import string
from collections import defaultdict

# --- CONFIGURATION ---
NUM_ELEMENTS = 1_000_000
DB_NAME = ":memory:"
random.seed(42)


def generate_random_string(length=5):
    return ''.join(random.choices(string.ascii_uppercase, k=length))


def setup_database():
    print(f"--- 1. SETTING UP FLEXIBLE SCHEMA ({NUM_ELEMENTS} elements) ---")
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Core normalized schema - properties are separate
    cursor.execute("CREATE TABLE elements (id INTEGER PRIMARY KEY)")
    cursor.execute("CREATE TABLE prop1 (elem_id INTEGER, value TEXT)")
    cursor.execute("CREATE TABLE prop2 (elem_id INTEGER, value TEXT)")
    cursor.execute("CREATE TABLE prop3 (elem_id INTEGER, value INTEGER)")

    # Indices on property tables
    cursor.execute("CREATE INDEX idx_p1_elem ON prop1(elem_id)")
    cursor.execute("CREATE INDEX idx_p2_elem ON prop2(elem_id)")
    cursor.execute("CREATE INDEX idx_p3_elem ON prop3(elem_id)")

    # SOLUTION 1: Materialized View (Manual in SQLite)
    # This is a cached JOIN result that you refresh when needed
    cursor.execute("""
        CREATE TABLE mv_element_props (
            elem_id INTEGER PRIMARY KEY,
            p1 TEXT,
            p2 TEXT,
            p3 INTEGER
        )
    """)
    # Composite index for fast grouping
    cursor.execute("CREATE INDEX idx_mv_group ON mv_element_props(p1, p2, p3)")

    # SOLUTION 2: Covering Index on Individual Properties
    # These allow index-only scans
    cursor.execute("CREATE INDEX idx_p1_covering ON prop1(elem_id, value)")
    cursor.execute("CREATE INDEX idx_p2_covering ON prop2(elem_id, value)")
    cursor.execute("CREATE INDEX idx_p3_covering ON prop3(elem_id, value)")

    print("  Generating data...")
    ids = [(i,) for i in range(NUM_ELEMENTS)]

    # Generate property data
    p1_choices = ['RED', 'BLUE', 'GREEN', 'YELLOW', 'BLACK']
    p2_choices = [generate_random_string() for _ in range(50)]

    p1_list = [random.choice(p1_choices) for _ in range(NUM_ELEMENTS)]
    p2_list = [random.choice(p2_choices) for _ in range(NUM_ELEMENTS)]
    p3_list = [random.randint(1, 10) for _ in range(NUM_ELEMENTS)]

    p1_data = list(zip(range(NUM_ELEMENTS), p1_list))
    p2_data = list(zip(range(NUM_ELEMENTS), p2_list))
    p3_data = list(zip(range(NUM_ELEMENTS), p3_list))

    print("  Inserting into normalized tables...")
    cursor.executemany("INSERT INTO elements VALUES (?)", ids)
    cursor.executemany("INSERT INTO prop1 VALUES (?,?)", p1_data)
    cursor.executemany("INSERT INTO prop2 VALUES (?,?)", p2_data)
    cursor.executemany("INSERT INTO prop3 VALUES (?,?)", p3_data)

    print("  Building materialized view...")
    # Populate the materialized view
    cursor.execute("""
        INSERT INTO mv_element_props (elem_id, p1, p2, p3)
        SELECT e.id, p1.value, p2.value, p3.value
        FROM elements e
        JOIN prop1 p1 ON e.id = p1.elem_id
        JOIN prop2 p2 ON e.id = p2.elem_id
        JOIN prop3 p3 ON e.id = p3.elem_id
    """)

    conn.commit()
    print("  Database Ready.\n")
    return conn, (p1_list, p2_list, p3_list)


def add_new_property(conn):
    """Demonstrates adding a new property without schema migration"""
    print("\n--- ADDING NEW PROPERTY (prop4) ---")
    cursor = conn.cursor()

    # Create new property table
    cursor.execute("CREATE TABLE prop4 (elem_id INTEGER, value TEXT)")
    cursor.execute("CREATE INDEX idx_p4_elem ON prop4(elem_id)")
    cursor.execute("CREATE INDEX idx_p4_covering ON prop4(elem_id, value)")

    # Add sample data
    p4_data = [(i, random.choice(['TYPE_A', 'TYPE_B', 'TYPE_C']))
               for i in range(100)]  # Just a sample
    cursor.executemany("INSERT INTO prop4 VALUES (?,?)", p4_data)

    conn.commit()
    print("  New property 'prop4' added successfully!")
    print("  To update materialized view, run refresh_materialized_view()")


def refresh_materialized_view(conn, property_columns=None):
    """
    Refresh the materialized view with current property data.
    Call this after bulk updates to properties.

    Args:
        property_columns: List of (table_name, column_alias) tuples
                         e.g., [('prop1', 'p1'), ('prop2', 'p2')]
    """
    if property_columns is None:
        property_columns = [('prop1', 'p1'), ('prop2', 'p2'), ('prop3', 'p3')]

    cursor = conn.cursor()

    # Drop and recreate (or use DELETE + INSERT for incremental)
    cursor.execute("DROP TABLE IF EXISTS mv_element_props")

    # Build dynamic schema
    col_defs = ['elem_id INTEGER PRIMARY KEY']
    col_defs.extend([f"{alias} TEXT" for _, alias in property_columns])

    cursor.execute(f"CREATE TABLE mv_element_props ({', '.join(col_defs)})")

    # Build dynamic JOIN query
    joins = []
    selects = ['e.id'] + [f"{alias}.value" for _, alias in property_columns]

    for table, alias in property_columns:
        joins.append(f"JOIN {table} {alias} ON e.id = {alias}.elem_id")

    query = f"""
        INSERT INTO mv_element_props
        SELECT {', '.join(selects)}
        FROM elements e
        {' '.join(joins)}
    """

    cursor.execute(query)

    # Recreate the composite index
    index_cols = [alias for _, alias in property_columns]
    cursor.execute(f"CREATE INDEX idx_mv_group ON mv_element_props({', '.join(index_cols)})")

    conn.commit()
    print(f"  Materialized view refreshed with columns: {[c[1] for c in property_columns]}")


def benchmark_approaches(conn, raw_data):
    print("--- 2. BENCHMARK: DIFFERENT APPROACHES ---")
    print("Goal: Group by (Prop1, Prop2, Prop3) and Count\n")

    p1_list, p2_list, p3_list = raw_data

    # --- BASELINE: Pure Python (No DB) ---
    start = time.perf_counter()
    python_groups = defaultdict(int)
    for p1, p2, p3 in zip(p1_list, p2_list, p3_list):
        python_groups[(p1, p2, p3)] += 1
    python_time = time.perf_counter() - start
    print(f"[0] BASELINE Python (in-memory): {python_time:.4f}s | Groups: {len(python_groups)}")

    # --- APPROACH 1: SQLite with JOINs (Normalized, Slow) ---
    start = time.perf_counter()
    results_norm = conn.execute("""
        SELECT p1.value, p2.value, p3.value, COUNT(*)
        FROM elements e
        JOIN prop1 p1 ON e.id = p1.elem_id
        JOIN prop2 p2 ON e.id = p2.elem_id
        JOIN prop3 p3 ON e.id = p3.elem_id
        GROUP BY p1.value, p2.value, p3.value
    """).fetchall()
    norm_time = time.perf_counter() - start
    print(f"[1] SQLite Normalized (JOINs): {norm_time:.4f}s | Groups: {len(results_norm)}")

    # --- APPROACH 2: Materialized View (Fast, Flexible) ---
    start = time.perf_counter()
    results_mv = conn.execute("""
        SELECT p1, p2, p3, COUNT(*)
        FROM mv_element_props
        GROUP BY p1, p2, p3
    """).fetchall()
    mv_time = time.perf_counter() - start
    print(f"[2] Materialized View (Cached): {mv_time:.4f}s | Groups: {len(results_mv)}")

    # --- APPROACH 3: Subquery with Index Optimization ---
    start = time.perf_counter()
    results_sub = conn.execute("""
        SELECT p1_val, p2_val, p3_val, COUNT(*)
        FROM (
            SELECT p1.value as p1_val, p2.value as p2_val, p3.value as p3_val
            FROM elements e
            JOIN prop1 p1 ON e.id = p1.elem_id
            JOIN prop2 p2 ON e.id = p2.elem_id
            JOIN prop3 p3 ON e.id = p3.elem_id
        )
        GROUP BY p1_val, p2_val, p3_val
    """).fetchall()
    sub_time = time.perf_counter() - start
    print(f"[3] Subquery Optimization: {sub_time:.4f}s | Groups: {len(results_sub)}")

    # --- Summary ---
    print(f"\n--- PERFORMANCE SUMMARY ---")
    print(f"Materialized View is {norm_time / mv_time:.1f}x faster than Normalized JOINs")
    print(f"Materialized View is {python_time / mv_time:.1f}x faster than Pure Python")
    print(f"\nTrade-offs:")
    print(f"  • Normalized: Flexible but slow ({norm_time:.3f}s)")
    print(f"  • Materialized View: Fast but needs refresh ({mv_time:.3f}s)")
    print(f"  • Memory baseline: Fastest but not persistent ({python_time:.3f}s)")


def demonstrate_flexibility(conn):
    """Show how easy it is to add/remove properties"""
    print("\n--- 3. DEMONSTRATING FLEXIBILITY ---")

    # Add a new property
    add_new_property(conn)

    # Query with the new property (just use JOINs for ad-hoc queries)
    result = conn.execute("""
        SELECT p1.value, p4.value, COUNT(*)
        FROM prop1 p1
        JOIN prop4 p4 ON p1.elem_id = p4.elem_id
        GROUP BY p1.value, p4.value
    """).fetchall()

    print(f"  Ad-hoc query with new prop4: {len(result)} groups found")

    # For frequently used combinations, refresh the materialized view
    print("\n  For frequently queried combinations, you can:")
    print("  1. Keep using JOINs (flexible, slower)")
    print("  2. Create a new materialized view for that specific combination")
    print("  3. Refresh main view to include new properties")


if __name__ == "__main__":
    conn, raw_data = setup_database()
    benchmark_approaches(conn, raw_data)
    demonstrate_flexibility(conn)

    print("\n--- BEST PRACTICES ---")
    print("✓ Keep normalized schema for flexibility")
    print("✓ Use materialized views for frequently-queried combinations")
    print("✓ Refresh materialized views after bulk updates (not per-row)")
    print("✓ Use JOINs for ad-hoc queries on new/rare property combinations")
    print("✓ Index properly: covering indexes on property tables")

    conn.close()