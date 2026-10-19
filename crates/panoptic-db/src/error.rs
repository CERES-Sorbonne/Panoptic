use thiserror::Error;

/// Every error of the crate.
#[derive(Debug, Error)]
pub enum DbError {
    #[error("sqlite: {0}")]
    Sqlite(#[from] rusqlite::Error),

    #[error("json: {0}")]
    Json(#[from] serde_json::Error),

    #[error("io: {0}")]
    Io(#[from] std::io::Error),

    /// A column held something the model cannot represent (wrong storage class, bad JSON…).
    #[error("decode error in {table}.{column}: {message}")]
    Decode { table: String, column: String, message: String },

    /// The caller passed something the operation cannot accept (unknown key, bad filter…).
    #[error("invalid input: {0}")]
    Invalid(String),

    #[error("database not found: {0}")]
    NotFound(String),

    #[error("migration of {db} failed at version {version}: {message}")]
    Migration { db: String, version: i64, message: String },

    /// A lock (mutex) guarding a connection was poisoned by a panicking thread.
    #[error("connection lock poisoned")]
    Poisoned,
}

pub type Result<T, E = DbError> = std::result::Result<T, E>;

impl DbError {
    pub(crate) fn invalid(msg: impl Into<String>) -> Self {
        DbError::Invalid(msg.into())
    }

    pub(crate) fn decode(table: &str, column: &str, message: impl Into<String>) -> Self {
        DbError::Decode { table: table.to_string(), column: column.to_string(), message: message.into() }
    }
}
