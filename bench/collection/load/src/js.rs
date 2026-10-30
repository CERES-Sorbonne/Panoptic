//! JavaScript semantics the TS engine relied on implicitly: UTF-16 string ordering, loose
//! equality / relational comparison with coercion, `Number(x)`, `String(n)`, `new Date(str)` and
//! `Date.UTC`. Ported so that filter / sort / group results are bit-identical to the frontend.

use std::borrow::Cow;
use std::cmp::Ordering;

// ── strings ──────────────────────────────────────────────────────────────────

/// `a < b` on JS strings compares UTF-16 code units. UTF-8 byte order equals code point order,
/// which differs only when a supplementary character (>= U+10000, a surrogate pair in UTF-16)
/// meets a BMP character in U+E000..U+FFFF at the first difference.
pub fn utf16_cmp(a: &str, b: &str) -> Ordering {
    if a.is_ascii() || b.is_ascii() {
        // An ASCII side means the first difference involves an ASCII char on at least one side,
        // or a prefix relation: byte order is exact there.
        let ab = a.as_bytes();
        let bb = b.as_bytes();
        let n = ab.len().min(bb.len());
        for i in 0..n {
            if ab[i] != bb[i] {
                // Both bytes could be non-ASCII only if neither string is ASCII.
                return ab[i].cmp(&bb[i]);
            }
        }
        return ab.len().cmp(&bb.len());
    }
    let mut ia = a.chars();
    let mut ib = b.chars();
    loop {
        match (ia.next(), ib.next()) {
            (None, None) => return Ordering::Equal,
            (None, Some(_)) => return Ordering::Less,
            (Some(_), None) => return Ordering::Greater,
            (Some(ca), Some(cb)) => {
                if ca == cb {
                    continue;
                }
                return first_unit(ca).cmp(&first_unit(cb)).then((ca as u32).cmp(&(cb as u32)));
            }
        }
    }
}

#[inline]
fn first_unit(c: char) -> u32 {
    let v = c as u32;
    if v >= 0x10000 { 0xD800 + ((v - 0x10000) >> 10) } else { v }
}

/// `String.prototype.toLowerCase` / `toLocaleLowerCase` (root locale).
#[inline]
pub fn lower(s: &str) -> Cow<'_, str> {
    if s.bytes().all(|b| !b.is_ascii_uppercase() && b < 0x80) {
        Cow::Borrowed(s)
    } else {
        Cow::Owned(s.to_lowercase())
    }
}

// ── numbers ──────────────────────────────────────────────────────────────────

fn is_js_space(c: char) -> bool {
    matches!(
        c,
        '\u{9}' | '\u{A}' | '\u{B}' | '\u{C}' | '\u{D}' | ' ' | '\u{A0}' | '\u{1680}'
            | '\u{2000}'..='\u{200A}'
            | '\u{2028}' | '\u{2029}' | '\u{202F}' | '\u{205F}' | '\u{3000}' | '\u{FEFF}'
    )
}

/// JS `Number(str)` (StringToNumber).
pub fn string_to_number(s: &str) -> f64 {
    let t = s.trim_matches(is_js_space);
    if t.is_empty() {
        return 0.0;
    }
    match t {
        "Infinity" | "+Infinity" => return f64::INFINITY,
        "-Infinity" => return f64::NEG_INFINITY,
        _ => {}
    }
    let b = t.as_bytes();
    if b.len() > 2 && b[0] == b'0' {
        let radix = match b[1] {
            b'x' | b'X' => 16,
            b'o' | b'O' => 8,
            b'b' | b'B' => 2,
            _ => 0,
        };
        if radix != 0 {
            let mut v = 0f64;
            for &c in &b[2..] {
                let d = match (c as char).to_digit(radix) {
                    Some(d) => d,
                    None => return f64::NAN,
                };
                v = v * radix as f64 + d as f64;
            }
            return v;
        }
    }
    // StrDecimalLiteral: [+-]? (digits [. digits?] | . digits) ([eE] [+-]? digits)?
    let mut i = 0;
    if i < b.len() && (b[i] == b'+' || b[i] == b'-') {
        i += 1;
    }
    let int_start = i;
    while i < b.len() && b[i].is_ascii_digit() {
        i += 1;
    }
    let mut digits = i - int_start;
    if i < b.len() && b[i] == b'.' {
        i += 1;
        let f = i;
        while i < b.len() && b[i].is_ascii_digit() {
            i += 1;
        }
        digits += i - f;
    }
    if digits == 0 {
        return f64::NAN;
    }
    if i < b.len() && (b[i] == b'e' || b[i] == b'E') {
        i += 1;
        if i < b.len() && (b[i] == b'+' || b[i] == b'-') {
            i += 1;
        }
        let e = i;
        while i < b.len() && b[i].is_ascii_digit() {
            i += 1;
        }
        if i == e {
            return f64::NAN;
        }
    }
    if i != b.len() {
        return f64::NAN;
    }
    t.parse::<f64>().unwrap_or(f64::NAN)
}

/// JS `String(n)` / `Number.prototype.toString()`.
pub fn number_to_string(x: f64) -> String {
    if x.is_nan() {
        return "NaN".into();
    }
    if x == 0.0 {
        return "0".into();
    }
    if x.is_infinite() {
        return if x > 0.0 { "Infinity".into() } else { "-Infinity".into() };
    }
    if x < 0.0 {
        return format!("-{}", number_to_string(-x));
    }
    if x.fract() == 0.0 && x < 1e21 {
        return format!("{}", x as u128);
    }
    let e = format!("{:e}", x);
    let (mant, exp) = e.split_once('e').unwrap();
    let exp: i32 = exp.parse().unwrap();
    let digits: String = mant.chars().filter(|c| *c != '.').collect();
    let k = digits.len() as i32;
    let n = exp + 1;
    if k <= n && n <= 21 {
        let mut s = digits.clone();
        for _ in 0..(n - k) {
            s.push('0');
        }
        s
    } else if 0 < n && n <= 21 {
        format!("{}.{}", &digits[..n as usize], &digits[n as usize..])
    } else if -6 < n && n <= 0 {
        let mut s = String::from("0.");
        for _ in 0..(-n) {
            s.push('0');
        }
        s.push_str(&digits);
        s
    } else {
        let sign = if n - 1 >= 0 { '+' } else { '-' };
        if k == 1 {
            format!("{}e{}{}", digits, sign, (n - 1).abs())
        } else {
            format!("{}.{}e{}{}", &digits[..1], &digits[1..], sign, (n - 1).abs())
        }
    }
}

// ── dates ────────────────────────────────────────────────────────────────────

pub const MS_PER_DAY: f64 = 86_400_000.0;

/// Days since 1970-01-01 of a proleptic Gregorian date (month 1..=12).
pub fn days_from_civil(y: i64, m: i64, d: i64) -> i64 {
    let y = if m <= 2 { y - 1 } else { y };
    let era = if y >= 0 { y } else { y - 399 } / 400;
    let yoe = y - era * 400;
    let mp = (m + 9) % 12;
    let doy = (153 * mp + 2) / 5 + d - 1;
    let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    era * 146097 + doe - 719468
}

/// (year, month 1..=12, day) of a day count since 1970-01-01.
pub fn civil_from_days(z: i64) -> (i64, i64, i64) {
    let z = z + 719468;
    let era = if z >= 0 { z } else { z - 146096 } / 146097;
    let doe = z - era * 146097;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    (if m <= 2 { y + 1 } else { y }, m, d)
}

/// `new Date(t)` time value: TimeClip (NaN beyond ±8.64e15, truncation toward zero).
pub fn time_clip(t: f64) -> f64 {
    if !t.is_finite() || t.abs() > 8.64e15 { f64::NAN } else { t.trunc() + 0.0 }
}

/// (UTC full year, UTC month 0..=11) of a time value — `getUTCFullYear` / `getUTCMonth`.
pub fn utc_year_month(t: f64) -> Option<(i64, i64)> {
    let t = time_clip(t);
    if t.is_nan() {
        return None;
    }
    let days = (t / MS_PER_DAY).floor() as i64;
    let (y, m, _) = civil_from_days(days);
    Some((y, m - 1))
}

fn to_integer(x: f64) -> f64 {
    if x.is_nan() { 0.0 } else { x.trunc() }
}

/// `Date.UTC(year, month, day)` with the spec's MakeDay overflow handling (month outside 0..11
/// rolls the year), then TimeClip.
pub fn date_utc(year: f64, month: f64, day: f64) -> f64 {
    if !year.is_finite() || !month.is_finite() || !day.is_finite() {
        return f64::NAN;
    }
    let y = to_integer(year);
    let m = to_integer(month);
    let dt = to_integer(day);
    let ym = y + (m / 12.0).floor();
    let mn = m.rem_euclid(12.0);
    if ym.abs() > 400_000.0 {
        return f64::NAN;
    }
    let days = days_from_civil(ym as i64, mn as i64 + 1, 1) as f64 + dt - 1.0;
    time_clip(days * MS_PER_DAY)
}

/// `+new Date(s)` for the ISO-8601 forms the app produces. Date-only forms are UTC (as in JS).
/// Date-time forms without an offset are local time in JS; here they are read as UTC (the
/// backend has no client time zone) — see ENGINE.md. Anything else is NaN.
pub fn parse_date(s: &str) -> f64 {
    let s = s.trim();
    let b = s.as_bytes();
    let mut i = 0;
    let num = |i: &mut usize, n: usize| -> Option<i64> {
        if *i + n > b.len() {
            return None;
        }
        let mut v = 0i64;
        for k in 0..n {
            let c = b[*i + k];
            if !c.is_ascii_digit() {
                return None;
            }
            v = v * 10 + (c - b'0') as i64;
        }
        *i += n;
        Some(v)
    };
    // year: YYYY or ±YYYYYY
    let year = if i < b.len() && (b[i] == b'+' || b[i] == b'-') {
        let neg = b[i] == b'-';
        i += 1;
        let y = match num(&mut i, 6) {
            Some(y) => y,
            None => return f64::NAN,
        };
        if neg { -y } else { y }
    } else {
        match num(&mut i, 4) {
            Some(y) => y,
            None => return f64::NAN,
        }
    };
    let mut month = 1;
    let mut day = 1;
    if i < b.len() && b[i] == b'-' {
        i += 1;
        month = match num(&mut i, 2) {
            Some(v) => v,
            None => return f64::NAN,
        };
        if i < b.len() && b[i] == b'-' {
            i += 1;
            day = match num(&mut i, 2) {
                Some(v) => v,
                None => return f64::NAN,
            };
        }
    }
    if !(1..=12).contains(&month) || !(1..=31).contains(&day) {
        return f64::NAN;
    }
    let (mut h, mut mi, mut sec, mut ms) = (0i64, 0i64, 0i64, 0i64);
    let mut offset_min = 0i64;
    if i < b.len() && (b[i] == b'T' || b[i] == b't' || b[i] == b' ') {
        i += 1;
        h = match num(&mut i, 2) {
            Some(v) => v,
            None => return f64::NAN,
        };
        if i >= b.len() || b[i] != b':' {
            return f64::NAN;
        }
        i += 1;
        mi = match num(&mut i, 2) {
            Some(v) => v,
            None => return f64::NAN,
        };
        if i < b.len() && b[i] == b':' {
            i += 1;
            sec = match num(&mut i, 2) {
                Some(v) => v,
                None => return f64::NAN,
            };
            if i < b.len() && (b[i] == b'.' || b[i] == b',') {
                i += 1;
                let start = i;
                let mut frac = 0i64;
                let mut nd = 0;
                while i < b.len() && b[i].is_ascii_digit() {
                    if nd < 3 {
                        frac = frac * 10 + (b[i] - b'0') as i64;
                        nd += 1;
                    }
                    i += 1;
                }
                if i == start {
                    return f64::NAN;
                }
                while nd < 3 {
                    frac *= 10;
                    nd += 1;
                }
                ms = frac;
            }
        }
        if i < b.len() {
            match b[i] {
                b'Z' | b'z' => i += 1,
                b'+' | b'-' => {
                    let neg = b[i] == b'-';
                    i += 1;
                    let oh = match num(&mut i, 2) {
                        Some(v) => v,
                        None => return f64::NAN,
                    };
                    if i < b.len() && b[i] == b':' {
                        i += 1;
                    }
                    let om = match num(&mut i, 2) {
                        Some(v) => v,
                        None => return f64::NAN,
                    };
                    offset_min = (oh * 60 + om) * if neg { -1 } else { 1 };
                }
                _ => return f64::NAN,
            }
        }
        if h > 24 || mi > 59 || sec > 59 || (h == 24 && (mi > 0 || sec > 0 || ms > 0)) {
            return f64::NAN;
        }
    }
    if i != b.len() {
        return f64::NAN;
    }
    let days = days_from_civil(year, month, day) as f64;
    let t = days * MS_PER_DAY
        + (h * 3_600_000 + mi * 60_000 + sec * 1000 + ms) as f64
        - (offset_min * 60_000) as f64;
    time_clip(t)
}

/// ISO string of a time value, as `Date.prototype.toISOString` (for debugging / dumps).
pub fn to_iso(t: f64) -> String {
    let t = time_clip(t);
    if t.is_nan() {
        return "Invalid Date".into();
    }
    let ms = t as i64;
    let days = ms.div_euclid(86_400_000);
    let rem = ms.rem_euclid(86_400_000);
    let (y, m, d) = civil_from_days(days);
    let ys = if (0..=9999).contains(&y) { format!("{:04}", y) } else if y < 0 { format!("-{:06}", -y) } else { format!("+{:06}", y) };
    format!(
        "{}-{:02}-{:02}T{:02}:{:02}:{:02}.{:03}Z",
        ys,
        m,
        d,
        rem / 3_600_000,
        rem / 60_000 % 60,
        rem / 1000 % 60,
        rem % 1000
    )
}

// ── loosely-typed values ─────────────────────────────────────────────────────

/// A JS value as the TS operator functions saw it.
#[derive(Debug, Clone, Copy)]
pub enum Jv<'a> {
    Undef,
    Null,
    Bool(bool),
    Num(f64),
    Str(&'a str),
    /// A tag column cell (`number[]`).
    Tags(&'a [i32]),
    /// An array coming from JSON (a filter value).
    Arr(&'a [serde_json::Value]),
    /// A plain object (from JSON).
    Obj,
}

impl<'a> Jv<'a> {
    pub fn from_json(v: &'a serde_json::Value) -> Jv<'a> {
        use serde_json::Value as V;
        match v {
            V::Null => Jv::Null,
            V::Bool(b) => Jv::Bool(*b),
            V::Number(n) => Jv::Num(n.as_f64().unwrap_or(f64::NAN)),
            V::String(s) => Jv::Str(s),
            V::Array(a) => Jv::Arr(a),
            V::Object(_) => Jv::Obj,
        }
    }

    /// `x == undefined` (true for null and undefined).
    pub fn is_nullish(&self) -> bool {
        matches!(self, Jv::Undef | Jv::Null)
    }

    /// The TS `isEmpty`: undefined, null, '' or an empty array.
    pub fn is_empty(&self) -> bool {
        match self {
            Jv::Undef | Jv::Null => true,
            Jv::Str(s) => s.is_empty(),
            Jv::Tags(t) => t.is_empty(),
            Jv::Arr(a) => a.is_empty(),
            _ => false,
        }
    }

    /// `!!x`.
    pub fn truthy(&self) -> bool {
        match self {
            Jv::Undef | Jv::Null => false,
            Jv::Bool(b) => *b,
            Jv::Num(n) => *n != 0.0 && !n.is_nan(),
            Jv::Str(s) => !s.is_empty(),
            Jv::Tags(_) | Jv::Arr(_) | Jv::Obj => true,
        }
    }

    fn is_object(&self) -> bool {
        matches!(self, Jv::Tags(_) | Jv::Arr(_) | Jv::Obj)
    }
}

/// A primitive (result of ToPrimitive).
#[derive(Debug, Clone)]
pub enum Prim<'a> {
    Undef,
    Null,
    Bool(bool),
    Num(f64),
    Str(Cow<'a, str>),
}

fn json_to_string(v: &serde_json::Value) -> String {
    use serde_json::Value as V;
    match v {
        V::Null => String::new(),
        V::Bool(b) => b.to_string(),
        V::Number(n) => number_to_string(n.as_f64().unwrap_or(f64::NAN)),
        V::String(s) => s.clone(),
        V::Array(a) => a.iter().map(json_to_string).collect::<Vec<_>>().join(","),
        V::Object(_) => "[object Object]".into(),
    }
}

pub fn to_primitive<'a>(v: &Jv<'a>) -> Prim<'a> {
    match *v {
        Jv::Undef => Prim::Undef,
        Jv::Null => Prim::Null,
        Jv::Bool(b) => Prim::Bool(b),
        Jv::Num(n) => Prim::Num(n),
        Jv::Str(s) => Prim::Str(Cow::Borrowed(s)),
        Jv::Tags(t) => Prim::Str(Cow::Owned(
            t.iter().map(|x| x.to_string()).collect::<Vec<_>>().join(","),
        )),
        Jv::Arr(a) => Prim::Str(Cow::Owned(
            a.iter().map(json_to_string).collect::<Vec<_>>().join(","),
        )),
        Jv::Obj => Prim::Str(Cow::Borrowed("[object Object]")),
    }
}

pub fn prim_to_number(p: &Prim) -> f64 {
    match p {
        Prim::Undef => f64::NAN,
        Prim::Null => 0.0,
        Prim::Bool(b) => *b as i32 as f64,
        Prim::Num(n) => *n,
        Prim::Str(s) => string_to_number(s),
    }
}

pub fn prim_to_string<'a>(p: &Prim<'a>) -> Cow<'a, str> {
    match p {
        Prim::Undef => Cow::Borrowed("undefined"),
        Prim::Null => Cow::Borrowed("null"),
        Prim::Bool(b) => Cow::Borrowed(if *b { "true" } else { "false" }),
        Prim::Num(n) => Cow::Owned(number_to_string(*n)),
        Prim::Str(s) => s.clone(),
    }
}

/// `Number(x)`.
pub fn to_number(v: &Jv) -> f64 {
    prim_to_number(&to_primitive(v))
}

/// `String(x)`.
pub fn to_string<'a>(v: &Jv<'a>) -> Cow<'a, str> {
    let p = to_primitive(v);
    match p {
        Prim::Str(s) => s,
        other => Cow::Owned(prim_to_string(&other).into_owned()),
    }
}

fn prim_loose_eq(a: &Prim, b: &Prim) -> bool {
    match (a, b) {
        (Prim::Undef | Prim::Null, Prim::Undef | Prim::Null) => true,
        (Prim::Undef | Prim::Null, _) | (_, Prim::Undef | Prim::Null) => false,
        (Prim::Num(x), Prim::Num(y)) => x == y,
        (Prim::Str(x), Prim::Str(y)) => x == y,
        (Prim::Bool(x), Prim::Bool(y)) => x == y,
        (Prim::Num(x), Prim::Str(s)) | (Prim::Str(s), Prim::Num(x)) => *x == string_to_number(s),
        (Prim::Bool(x), other) | (other, Prim::Bool(x)) => {
            prim_loose_eq(&Prim::Num(*x as i32 as f64), other)
        }
    }
}

/// JS `a == b`.
pub fn loose_eq(a: &Jv, b: &Jv) -> bool {
    if a.is_object() && b.is_object() {
        // Two distinct objects (a cell array and a filter array) are never `==`.
        return false;
    }
    if a.is_nullish() || b.is_nullish() {
        return a.is_nullish() && b.is_nullish();
    }
    prim_loose_eq(&to_primitive(a), &to_primitive(b))
}

/// Abstract relational comparison `a < b`: `Some(bool)`, or `None` for "undefined" (a NaN).
pub fn rel_less(a: &Jv, b: &Jv) -> Option<bool> {
    let pa = to_primitive(a);
    let pb = to_primitive(b);
    if let (Prim::Str(x), Prim::Str(y)) = (&pa, &pb) {
        return Some(utf16_cmp(x, y) == Ordering::Less);
    }
    let x = prim_to_number(&pa);
    let y = prim_to_number(&pb);
    if x.is_nan() || y.is_nan() { None } else { Some(x < y) }
}

pub fn js_lt(a: &Jv, b: &Jv) -> bool {
    rel_less(a, b) == Some(true)
}
pub fn js_gt(a: &Jv, b: &Jv) -> bool {
    rel_less(b, a) == Some(true)
}
pub fn js_le(a: &Jv, b: &Jv) -> bool {
    rel_less(b, a) == Some(false)
}
pub fn js_ge(a: &Jv, b: &Jv) -> bool {
    rel_less(a, b) == Some(false)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn numbers() {
        assert_eq!(string_to_number(""), 0.0);
        assert_eq!(string_to_number(" 12 "), 12.0);
        assert_eq!(string_to_number("0x10"), 16.0);
        assert!(string_to_number("abc").is_nan());
        assert!(string_to_number("inf").is_nan());
        assert_eq!(string_to_number("1e3"), 1000.0);
        assert_eq!(string_to_number(".5"), 0.5);
        assert!(string_to_number(".").is_nan());
        assert_eq!(number_to_string(1.5), "1.5");
        assert_eq!(number_to_string(100.0), "100");
        assert_eq!(number_to_string(1e21), "1e+21");
        assert_eq!(number_to_string(1e-7), "1e-7");
        assert_eq!(number_to_string(0.000001), "0.000001");
        assert_eq!(number_to_string(123.456), "123.456");
        assert_eq!(number_to_string(-2.0), "-2");
    }

    #[test]
    fn dates() {
        assert_eq!(parse_date("1970-01-01"), 0.0);
        assert_eq!(parse_date("2024-01-15T10:30:00.000Z"), 1705314600000.0);
        assert_eq!(parse_date("2024-01-15T10:30:00+01:00"), 1705311000000.0);
        assert!(parse_date("hello").is_nan());
        assert_eq!(date_utc(2024.0, 0.0, 1.0), 1704067200000.0);
        // month overflow rolls the year, like Date.UTC
        assert_eq!(date_utc(2023.0, 12.0, 1.0), 1704067200000.0);
        assert_eq!(utc_year_month(1705314600000.0), Some((2024, 0)));
        assert_eq!(to_iso(1705314600000.0), "2024-01-15T10:30:00.000Z");
        for d in [-1000000i64, -1, 0, 1, 19000, 400000] {
            let (y, m, dd) = civil_from_days(d);
            assert_eq!(days_from_civil(y, m, dd), d);
        }
    }

    #[test]
    fn compare() {
        assert_eq!(utf16_cmp("a", "b"), Ordering::Less);
        assert_eq!(utf16_cmp("ab", "a"), Ordering::Greater);
        // U+FF5E (BMP, high) vs U+1F600 (surrogate pair D83D...): UTF-16 puts the emoji first
        assert_eq!(utf16_cmp("\u{FF5E}", "\u{1F600}"), Ordering::Greater);
        assert!(loose_eq(&Jv::Num(5.0), &Jv::Str("5")));
        assert!(loose_eq(&Jv::Null, &Jv::Undef));
        assert!(!loose_eq(&Jv::Null, &Jv::Num(0.0)));
        assert!(loose_eq(&Jv::Bool(false), &Jv::Num(0.0)));
        assert!(js_lt(&Jv::Str("10"), &Jv::Str("9")));
        assert!(!js_lt(&Jv::Num(10.0), &Jv::Str("9")));
        assert!(!js_ge(&Jv::Num(1.0), &Jv::Str("x")));
    }
}
