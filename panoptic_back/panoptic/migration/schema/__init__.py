"""The target's own schema, copied into the migrator.

The four `.sql` files here are the `CREATE TABLE` statements the target's
`create.py` files produce (`~/panoptic/panoptic_back/panoptic/core/databases/
{panoptic,project,data,media}/create.py` on `rework-front`), captured by task
0.1 into `analysis/target_schema.sql` and split per database. Keeping a copy is
what makes the migrator stdlib-only and runnable without a panoptic install.

Two things `create.py` does *not* contain and this module adds:

* `_version` -- created by `SQLiteWriter.start()` in **every** one of the four
  DBs, with `('db_version', 1)` (TARGET_NOTES section 2). A DB written without
  it is topped up on open, but writing it makes the output self-describing.
* the connection pragmas the target applies on open.

Because the copy can drift from upstream, `check_upstream()` is an advisory
fingerprint check -- see `migrator/schema/check.py`. It never fails a run.
"""

from __future__ import annotations

import os
import sqlite3

SCHEMA_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAMES = ("panoptic", "project", "data", "media")

#: `SQLiteWriter.start()` writes this before any table of `desc.tables`.
VERSION_SQL = (
    "CREATE TABLE IF NOT EXISTS _version ("
    " key TEXT PRIMARY KEY NOT NULL,"
    " value INTEGER NOT NULL);\n"
    "INSERT OR IGNORE INTO _version (key, value) VALUES ('db_version', 1);\n"
)

#: applied by the target on every connection open
PRAGMAS = ("PRAGMA journal_mode=WAL",
           "PRAGMA synchronous=NORMAL",
           "PRAGMA temp_store=MEMORY",
           "PRAGMA foreign_keys=1")


def schema_path(name):
    if name not in DB_NAMES:
        raise KeyError("unknown target database %r" % (name,))
    return os.path.join(SCHEMA_DIR, "%s.sql" % name)


def schema_sql(name):
    with open(schema_path(name), encoding="utf-8") as fh:
        return fh.read()


def create_db(path, name):
    """Create `path` as an empty target DB of kind `name`, and return the conn.

    The caller owns the connection (commit + close). `_version` first, then the
    tables -- the same order `SQLiteWriter.start()` uses.
    """
    conn = sqlite3.connect(path)
    for pragma in PRAGMAS:
        conn.execute(pragma)
    conn.executescript(VERSION_SQL)
    conn.executescript(schema_sql(name))
    conn.commit()
    return conn


def table_names(name):
    """The tables `name`'s schema creates (parsed out of the copied SQL)."""
    import re
    return sorted(set(re.findall(
        r"CREATE TABLE IF NOT EXISTS\s+(\w+)", schema_sql(name))))


def checkpoint(path):
    """Fold the WAL back into the DB file and drop the `-wal`/`-shm` sidecars.

    The target opens its DBs in WAL mode, so we write in WAL mode too; but a
    freshly migrated project folder should be a set of self-contained files, not
    a DB plus two sidecars left behind because the last connection to touch it
    was read-only (a read-only connection cannot checkpoint).

    Closing the last connection only *usually* removes the sidecars: on older
    SQLite builds (3.43, the one shipped with the macOS system python 3.9) they
    survive the close, and a later read-only open of the same folder then fails
    with "unable to open database file". So the truncated files are unlinked
    explicitly. That is safe precisely because the checkpoint has already
    folded every page back into the main DB -- and only then.
    """
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        # Back to a rollback journal: this is what actually deletes the `-wal`,
        # and it also makes the file openable `mode=ro` on old SQLite, which
        # refuses to create the `-shm` a WAL reader needs. The target re-enables
        # WAL itself on every open (`PRAGMAS`), and journal mode lives in the
        # file header, not in the data -- so nothing is lost by handing over a
        # file in DELETE mode.
        conn.execute("PRAGMA journal_mode=DELETE")
    finally:
        conn.close()
    for suffix in ("-wal", "-shm"):
        try:
            os.remove(path + suffix)
        except OSError:
            pass
