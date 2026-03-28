def exec_bulk_delete(tx, table: str, field: str, ids: set):
    """
    Optimized bulk deletion using a temporary table and index for high-volume IDs.
    """
    if not ids:
        return

    # Create temporary staging table for IDs
    tx.execute("CREATE TEMP TABLE IF NOT EXISTS _del_ids (id ANY)")
    tx.execute("DELETE FROM _del_ids")

    # Fast-load IDs into the temporary table
    tx.executemany("INSERT INTO _del_ids VALUES (?)", [(i,) for i in ids])

    # Optional index for very large sets to speed up the subquery join
    tx.execute("CREATE INDEX IF NOT EXISTS _idx_del_ids ON _del_ids(id)")

    # Execute deletion based on the specified field
    tx.execute(f"DELETE FROM {table} WHERE {field} IN (SELECT id FROM _del_ids)")

    # Cleanup temporary resources
    tx.execute("DROP TABLE _del_ids")