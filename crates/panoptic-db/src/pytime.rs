//! Naive datetimes stored the way Python's sqlite3 adapter stores them.
//!
//! On disk (`TIMESTAMP` columns: `commits.timestamp`, `files.created_at`) a datetime is the
//! TEXT `datetime.isoformat(" ")`: `YYYY-MM-DD HH:MM:SS` plus `.ffffff` only when the
//! microseconds are non-zero. No timezone (Python always writes naive local time).
//!
//! Over the API (serde) it is what `msgspec.json` / `orjson` emit for a naive datetime:
//! `YYYY-MM-DDTHH:MM:SS[.ffffff]`.

use std::fmt;

use chrono::{Datelike, NaiveDate, NaiveDateTime, NaiveTime, Timelike};
use rusqlite::types::{FromSql, FromSqlError, FromSqlResult, ToSql, ToSqlOutput, ValueRef};
use serde::{Deserialize, Deserializer, Serialize, Serializer};

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct PyDateTime(pub NaiveDateTime);

impl PyDateTime {
    /// `datetime.datetime.now()` (local, naive, microsecond precision).
    pub fn now() -> Self {
        let now = chrono::Local::now().naive_local();
        PyDateTime(truncate_micros(now))
    }

    pub fn from_ymd_hms_micro(y: i32, mo: u32, d: u32, h: u32, mi: u32, s: u32, us: u32) -> Option<Self> {
        let date = NaiveDate::from_ymd_opt(y, mo, d)?;
        let time = NaiveTime::from_hms_micro_opt(h, mi, s, us)?;
        Some(PyDateTime(NaiveDateTime::new(date, time)))
    }

    fn micros(&self) -> u32 {
        self.0.nanosecond() / 1000
    }

    fn format_with(&self, sep: char) -> String {
        let d = self.0;
        let mut s = format!(
            "{:04}-{:02}-{:02}{}{:02}:{:02}:{:02}",
            d.year(),
            d.month(),
            d.day(),
            sep,
            d.hour(),
            d.minute(),
            d.second()
        );
        let us = self.micros();
        if us != 0 {
            s.push_str(&format!(".{:06}", us));
        }
        s
    }

    /// `datetime.isoformat(" ")` — the on-disk form.
    pub fn to_db_string(&self) -> String {
        self.format_with(' ')
    }

    /// `datetime.isoformat()` — the API (msgspec/orjson) form.
    pub fn to_iso_string(&self) -> String {
        self.format_with('T')
    }

    /// Parse the Python adapter's format. Accepts `' '` or `'T'` between date and time and
    /// any number of fractional digits (padded / truncated to microseconds, like CPython's
    /// converter). A trailing `Z` or `+HH:MM` offset is ignored.
    pub fn parse(s: &str) -> Option<Self> {
        let s = s.trim();
        let (date, time) = s.split_once(' ').or_else(|| s.split_once('T'))?;
        let mut dp = date.split('-');
        let y: i32 = dp.next()?.parse().ok()?;
        let mo: u32 = dp.next()?.parse().ok()?;
        let d: u32 = dp.next()?.parse().ok()?;
        if dp.next().is_some() {
            return None;
        }
        let time = time.trim_end_matches('Z');
        let time = match time.find(['+', '-']) {
            Some(i) => &time[..i],
            None => time,
        };
        let (hms, frac) = match time.split_once('.') {
            Some((a, b)) => (a, Some(b)),
            None => (time, None),
        };
        let mut tp = hms.split(':');
        let h: u32 = tp.next()?.parse().ok()?;
        let mi: u32 = tp.next()?.parse().ok()?;
        let sec: u32 = tp.next()?.parse().ok()?;
        let us = match frac {
            Some(f) => {
                let mut f: String = f.chars().take(6).collect();
                while f.len() < 6 {
                    f.push('0');
                }
                f.parse().ok()?
            }
            None => 0,
        };
        Self::from_ymd_hms_micro(y, mo, d, h, mi, sec, us)
    }
}

fn truncate_micros(d: NaiveDateTime) -> NaiveDateTime {
    let us = d.nanosecond() / 1000;
    d.with_nanosecond(us * 1000).unwrap_or(d)
}

impl fmt::Display for PyDateTime {
    /// Python `str(datetime)` (== the on-disk form).
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.to_db_string())
    }
}

impl From<NaiveDateTime> for PyDateTime {
    fn from(d: NaiveDateTime) -> Self {
        PyDateTime(truncate_micros(d))
    }
}

impl ToSql for PyDateTime {
    fn to_sql(&self) -> rusqlite::Result<ToSqlOutput<'_>> {
        Ok(ToSqlOutput::from(self.to_db_string()))
    }
}

impl FromSql for PyDateTime {
    fn column_result(value: ValueRef<'_>) -> FromSqlResult<Self> {
        let text = match value {
            ValueRef::Text(t) | ValueRef::Blob(t) => std::str::from_utf8(t).map_err(|e| FromSqlError::Other(Box::new(e)))?,
            _ => return Err(FromSqlError::InvalidType),
        };
        PyDateTime::parse(text).ok_or_else(|| FromSqlError::Other(format!("bad timestamp {text:?}").into()))
    }
}

impl Serialize for PyDateTime {
    fn serialize<S: Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
        s.serialize_str(&self.to_iso_string())
    }
}

impl<'de> Deserialize<'de> for PyDateTime {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        let s = String::deserialize(d)?;
        PyDateTime::parse(&s).ok_or_else(|| serde::de::Error::custom(format!("invalid datetime {s:?}")))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn formats_like_python() {
        let d = PyDateTime::from_ymd_hms_micro(2024, 1, 2, 3, 4, 5, 678000).unwrap();
        assert_eq!(d.to_db_string(), "2024-01-02 03:04:05.678000");
        assert_eq!(d.to_iso_string(), "2024-01-02T03:04:05.678000");
        let z = PyDateTime::from_ymd_hms_micro(2024, 1, 2, 3, 4, 5, 0).unwrap();
        assert_eq!(z.to_db_string(), "2024-01-02 03:04:05");
        assert_eq!(PyDateTime::parse("2024-01-02 03:04:05.5").unwrap().micros(), 500000);
        assert_eq!(PyDateTime::parse("2024-01-02 03:04:05").unwrap(), z);
        assert_eq!(PyDateTime::parse("2024-01-02T03:04:05.678").unwrap(), d);
    }
}
