"""SQLite connections for plugin processes.

Reads use read-only connections (`mode=ro` URI + `PRAGMA query_only`) in autocommit mode, so a
read transaction lasts one statement and never pins the WAL. Plugins never checkpoint and never
change the journal mode: the backend owns both.

Writes use their own connection: `BEGIN IMMEDIATE` (take the write lock up front, as the
reference does), short transactions, a busy timeout so the plugin waits for the backend writer
instead of failing.
"""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

BUSY_TIMEOUT_S = 30.0


def connect_readonly(path: str | Path, timeout: float = BUSY_TIMEOUT_S) -> sqlite3.Connection:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Database not found: {path}")
    uri = path.resolve().as_uri() + '?mode=ro'
    try:
        conn = sqlite3.connect(uri, uri=True, timeout=timeout, isolation_level=None,
                               check_same_thread=False)
        conn.execute('SELECT 1 FROM sqlite_master LIMIT 1').fetchall()
    except sqlite3.OperationalError:
        # A WAL database whose -shm cannot be created read-only (no other connection open and a
        # read-only folder is not expected; SQLITE_READONLY_CANTINIT): fall back to a normal
        # connection that refuses writes.
        conn = sqlite3.connect(str(path), timeout=timeout, isolation_level=None,
                               check_same_thread=False)
    conn.execute('PRAGMA query_only = ON')
    conn.execute(f'PRAGMA busy_timeout = {int(timeout * 1000)}')
    return conn


def connect_writer(path: str | Path, timeout: float = BUSY_TIMEOUT_S) -> sqlite3.Connection:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Database not found: {path}")
    conn = sqlite3.connect(str(path), timeout=timeout, isolation_level=None, check_same_thread=False)
    conn.execute(f'PRAGMA busy_timeout = {int(timeout * 1000)}')
    conn.execute('PRAGMA foreign_keys = 1')
    return conn


@contextmanager
def write_transaction(conn: sqlite3.Connection):
    """BEGIN IMMEDIATE ... COMMIT, rolled back on any exception (BaseException included, so an
    interrupted task releases the write lock)."""
    cur = conn.cursor()
    cur.execute('BEGIN IMMEDIATE')
    try:
        yield cur
        conn.execute('COMMIT')
    except BaseException:
        conn.execute('ROLLBACK')
        raise
    finally:
        cur.close()


class ConnectionPool:
    """One read-only connection per (thread, database); closed together."""

    def __init__(self, paths: dict[str, Path]):
        self.paths = {k: Path(v) for k, v in paths.items()}
        self._local = threading.local()
        self._all: list[sqlite3.Connection] = []
        self._lock = threading.Lock()
        self._writers: dict[str, sqlite3.Connection] = {}
        self._writer_locks: dict[str, threading.Lock] = {k: threading.Lock() for k in self.paths}

    def read(self, db: str) -> sqlite3.Connection:
        conns = getattr(self._local, 'conns', None)
        if conns is None:
            conns = self._local.conns = {}
        conn = conns.get(db)
        if conn is None:
            conn = connect_readonly(self.paths[db])
            conns[db] = conn
            with self._lock:
                self._all.append(conn)
        return conn

    @contextmanager
    def write(self, db: str):
        """A write transaction on `db`, serialized inside this process."""
        with self._writer_locks[db]:
            conn = self._writers.get(db)
            if conn is None:
                conn = self._writers[db] = connect_writer(self.paths[db])
            with write_transaction(conn) as cur:
                yield cur

    def close(self) -> None:
        with self._lock:
            conns, self._all = self._all, []
            writers, self._writers = list(self._writers.values()), {}
        for c in conns + writers:
            try:
                c.close()
            except Exception:
                pass
        self._local = threading.local()
