//! Connection setup shared by the four databases (port of `sqlite_db.py` / `sqlite_reader.py`).
//!
//! * **Writer**: one per database and process. WAL, `synchronous=NORMAL`, `foreign_keys=1`,
//!   `busy_timeout`. Opening it creates the file, the `_version` table, runs the version
//!   migrations and creates missing tables — all inside one `BEGIN IMMEDIATE` so two processes
//!   opening a fresh project at the same time cannot both seed it. Every write is a
//!   `BEGIN IMMEDIATE` transaction ([`immediate`]).
//! * **Readers**: cheap, any number, `query_only=ON`. In WAL mode they never block the writer
//!   and see a consistent snapshot per statement / transaction.

use std::path::{Path, PathBuf};
use std::sync::{Mutex, MutexGuard};
use std::time::Duration;

use rusqlite::{Connection, OpenFlags, Transaction, TransactionBehavior};

use crate::error::{DbError, Result};
use crate::schema::table_exists;

/// How long a statement waits on a lock held by another connection / process.
pub const BUSY_TIMEOUT: Duration = Duration::from_secs(30);

pub const VERSION_TABLE: &str = "_version";
pub const VERSION_KEY: &str = "db_version";

pub type MigrationFn = fn(&Connection) -> Result<()>;

/// `DbDescription`: target version, tables (name → creation script) and migrations
/// (`from_version` → step to `from_version + 1`).
pub struct DbDescription {
    pub name: &'static str,
    pub version: i64,
    pub tables: Vec<(&'static str, String)>,
    pub migrations: Vec<(i64, MigrationFn)>,
}

fn apply_common_pragmas(conn: &Connection) -> Result<()> {
    conn.busy_timeout(BUSY_TIMEOUT)?;
    let _: String = conn.query_row("PRAGMA journal_mode=WAL", [], |r| r.get(0))?;
    conn.execute_batch("PRAGMA synchronous=NORMAL; PRAGMA temp_store=MEMORY; PRAGMA foreign_keys=1;")?;
    Ok(())
}

/// Open (creating if needed) the writer connection of a database and bring its schema up to
/// date — `SQLiteWriter.start()`.
pub fn open_writer(path: &Path, desc: &DbDescription) -> Result<Connection> {
    if let Some(parent) = path.parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent)?;
        }
    }
    let mut conn = Connection::open(path)?;
    apply_common_pragmas(&conn)?;
    immediate(&mut conn, |tx| {
        tx.execute(
            &format!(
                "CREATE TABLE IF NOT EXISTS {VERSION_TABLE} (\n                key TEXT PRIMARY KEY NOT NULL,\n                value INTEGER NOT NULL\n            );"
            ),
            [],
        )?;
        tx.execute(&format!("INSERT OR IGNORE INTO {VERSION_TABLE} (key, value) VALUES (?, 1)"), [VERSION_KEY])?;
        run_migrations(tx, desc)?;
        for (name, sql) in &desc.tables {
            if !table_exists(tx, name)? {
                tx.execute_batch(sql)?;
            }
        }
        Ok(())
    })?;
    Ok(conn)
}

fn run_migrations(conn: &Connection, desc: &DbDescription) -> Result<()> {
    loop {
        let current = db_version(conn)?;
        if current >= desc.version {
            return Ok(());
        }
        let Some((_, step)) = desc.migrations.iter().find(|(v, _)| *v == current) else {
            tracing::warn!("no migration path for {} v{current}; update stopped", desc.name);
            return Ok(());
        };
        tracing::info!("migrating {} from v{current} to v{}", desc.name, current + 1);
        step(conn).map_err(|e| DbError::Migration { db: desc.name.into(), version: current, message: e.to_string() })?;
        conn.execute(&format!("UPDATE {VERSION_TABLE} SET value = ? WHERE key = ?"), rusqlite::params![current + 1, VERSION_KEY])?;
    }
}

/// The `_version.db_version` of an open database (1 when the table is missing).
pub fn db_version(conn: &Connection) -> Result<i64> {
    if !table_exists(conn, VERSION_TABLE)? {
        return Ok(1);
    }
    let v: Option<i64> = conn
        .query_row(&format!("SELECT value FROM {VERSION_TABLE} WHERE key = ?"), [VERSION_KEY], |r| r.get(0))
        .ok();
    Ok(v.unwrap_or(1))
}

/// Open a read-only connection — `SQLiteReader.start()`. The file must exist.
pub fn open_reader(path: &Path) -> Result<Connection> {
    if !path.exists() {
        return Err(DbError::NotFound(path.display().to_string()));
    }
    let conn = Connection::open_with_flags(path, OpenFlags::SQLITE_OPEN_READ_WRITE | OpenFlags::SQLITE_OPEN_NO_MUTEX | OpenFlags::SQLITE_OPEN_URI)?;
    conn.busy_timeout(BUSY_TIMEOUT)?;
    conn.execute_batch(
        "PRAGMA query_only = ON; PRAGMA cache_size = -100000; PRAGMA temp_store = MEMORY; PRAGMA mmap_size = 30000000000;",
    )?;
    Ok(conn)
}

/// Run `f` inside `BEGIN IMMEDIATE … COMMIT` (rolled back on error). The write lock is taken
/// up front, so two writers (threads or processes) serialize instead of deadlocking on an
/// upgrade.
pub fn immediate<T>(conn: &mut Connection, f: impl FnOnce(&Transaction<'_>) -> Result<T>) -> Result<T> {
    let tx = conn.transaction_with_behavior(TransactionBehavior::Immediate)?;
    let out = f(&tx)?;
    tx.commit()?;
    Ok(out)
}

/// A writer connection behind a mutex: `Send + Sync`, one statement stream at a time.
/// Dropping it checkpoints the WAL (`wal_checkpoint(TRUNCATE)`, like Python's `close()`).
pub struct WriterConn {
    path: PathBuf,
    conn: Mutex<Connection>,
}

impl WriterConn {
    pub fn open(path: impl AsRef<Path>, desc: &DbDescription) -> Result<Self> {
        let path = path.as_ref().to_path_buf();
        let conn = open_writer(&path, desc)?;
        Ok(WriterConn { path, conn: Mutex::new(conn) })
    }

    pub fn path(&self) -> &Path {
        &self.path
    }

    pub fn lock(&self) -> Result<MutexGuard<'_, Connection>> {
        self.conn.lock().map_err(|_| DbError::Poisoned)
    }

    /// Run `f` in a `BEGIN IMMEDIATE` transaction on the writer connection.
    pub fn tx<T>(&self, f: impl FnOnce(&Transaction<'_>) -> Result<T>) -> Result<T> {
        let mut g = self.lock()?;
        immediate(&mut g, f)
    }

    /// Run `f` on the writer connection outside a transaction (reads).
    pub fn read<T>(&self, f: impl FnOnce(&Connection) -> Result<T>) -> Result<T> {
        let g = self.lock()?;
        f(&g)
    }

    /// `PRAGMA wal_checkpoint(TRUNCATE)`.
    pub fn checkpoint(&self) -> Result<()> {
        let g = self.lock()?;
        g.query_row("PRAGMA wal_checkpoint(TRUNCATE)", [], |_| Ok(()))?;
        Ok(())
    }
}

impl Drop for WriterConn {
    fn drop(&mut self) {
        if let Ok(g) = self.conn.get_mut() {
            // Don't hang at shutdown if another process holds a read transaction.
            let _ = g.busy_timeout(Duration::from_millis(500));
            let _ = g.query_row("PRAGMA wal_checkpoint(TRUNCATE)", [], |_| Ok(()));
        }
    }
}

/// A tiny pool of idle values (reader connections). `get` reuses an idle one or creates a new
/// one; the guard puts it back on drop (up to `max_idle`).
pub struct Pool<T> {
    idle: Mutex<Vec<T>>,
    max_idle: usize,
    make: Box<dyn Fn() -> Result<T> + Send + Sync>,
}

impl<T> Pool<T> {
    pub fn new(max_idle: usize, make: impl Fn() -> Result<T> + Send + Sync + 'static) -> Self {
        Pool { idle: Mutex::new(Vec::new()), max_idle, make: Box::new(make) }
    }

    pub fn get(&self) -> Result<Pooled<'_, T>> {
        let item = self.idle.lock().map_err(|_| DbError::Poisoned)?.pop();
        let item = match item {
            Some(i) => i,
            None => (self.make)()?,
        };
        Ok(Pooled { pool: self, item: Some(item) })
    }
}

pub struct Pooled<'a, T> {
    pool: &'a Pool<T>,
    item: Option<T>,
}

impl<T> std::ops::Deref for Pooled<'_, T> {
    type Target = T;
    fn deref(&self) -> &T {
        self.item.as_ref().expect("pooled item present until drop")
    }
}

impl<T> std::ops::DerefMut for Pooled<'_, T> {
    fn deref_mut(&mut self) -> &mut T {
        self.item.as_mut().expect("pooled item present until drop")
    }
}

impl<T> Drop for Pooled<'_, T> {
    fn drop(&mut self) {
        if let Some(item) = self.item.take() {
            if let Ok(mut idle) = self.pool.idle.lock() {
                if idle.len() < self.pool.max_idle {
                    idle.push(item);
                }
            }
        }
    }
}
