//! Python-compatible JSON text and value semantics.
//!
//! The Python backend writes every JSON column with `json.dumps(value)` (default separators
//! `", "` / `": "`, `ensure_ascii=True`, floats in `repr` form) and encodes entity keys of the
//! generic version log with `json.dumps(pk, separators=(',', ':'))`. Entity keys are compared
//! *textually* in SQL, so the Rust side must produce exactly the same bytes. [`dumps`] and
//! [`dumps_compact`] reproduce CPython's output byte for byte for every value representable in
//! a [`serde_json::Value`].
//!
//! [`py_eq`] reproduces Python's `==` on decoded JSON values (`1 == 1.0 == True`), which the
//! writer uses to decide whether a write changes anything.

use serde_json::{Number, Value};

/// `json.dumps(value)` — default separators, `ensure_ascii=True`.
pub fn dumps(v: &Value) -> String {
    let mut out = String::with_capacity(32);
    write_value(&mut out, v, ", ", ": ");
    out
}

/// `json.dumps(value, separators=(',', ':'))` — used for `entity_log.entity_key`.
pub fn dumps_compact(v: &Value) -> String {
    let mut out = String::with_capacity(16);
    write_value(&mut out, v, ",", ":");
    out
}

fn write_value(out: &mut String, v: &Value, item_sep: &str, key_sep: &str) {
    match v {
        Value::Null => out.push_str("null"),
        Value::Bool(true) => out.push_str("true"),
        Value::Bool(false) => out.push_str("false"),
        Value::Number(n) => write_number(out, n),
        Value::String(s) => write_str(out, s),
        Value::Array(a) => {
            out.push('[');
            for (i, x) in a.iter().enumerate() {
                if i > 0 {
                    out.push_str(item_sep);
                }
                write_value(out, x, item_sep, key_sep);
            }
            out.push(']');
        }
        Value::Object(m) => {
            out.push('{');
            for (i, (k, x)) in m.iter().enumerate() {
                if i > 0 {
                    out.push_str(item_sep);
                }
                write_str(out, k);
                out.push_str(key_sep);
                write_value(out, x, item_sep, key_sep);
            }
            out.push('}');
        }
    }
}

fn write_number(out: &mut String, n: &Number) {
    if let Some(i) = n.as_i64() {
        out.push_str(&i.to_string());
    } else if let Some(u) = n.as_u64() {
        out.push_str(&u.to_string());
    } else if let Some(f) = n.as_f64() {
        out.push_str(&float_repr(f));
    }
}

/// CPython `repr(float)` (and therefore `json.dumps(float)`).
pub fn float_repr(f: f64) -> String {
    if f.is_nan() {
        return "NaN".into();
    }
    if f.is_infinite() {
        return if f > 0.0 { "Infinity".into() } else { "-Infinity".into() };
    }
    if f == 0.0 {
        return if f.is_sign_negative() { "-0.0".into() } else { "0.0".into() };
    }
    // Rust's `{:e}` without precision prints the shortest round-tripping digits, the same
    // digits CPython's repr uses; only the layout differs.
    let s = format!("{:e}", f);
    let (neg, s) = match s.strip_prefix('-') {
        Some(rest) => (true, rest),
        None => (false, s.as_str()),
    };
    let (mant, exp) = s.split_once('e').expect("LowerExp always has an exponent");
    let exp: i32 = exp.parse().expect("integer exponent");
    let digits: String = mant.chars().filter(|c| *c != '.').collect();
    let n = digits.len() as i32;
    let decpt = exp + 1;
    let mut out = String::with_capacity(24);
    if neg {
        out.push('-');
    }
    if (-4..16).contains(&exp) {
        if decpt <= 0 {
            out.push_str("0.");
            for _ in 0..(-decpt) {
                out.push('0');
            }
            out.push_str(&digits);
        } else if decpt >= n {
            out.push_str(&digits);
            for _ in 0..(decpt - n) {
                out.push('0');
            }
            out.push_str(".0");
        } else {
            out.push_str(&digits[..decpt as usize]);
            out.push('.');
            out.push_str(&digits[decpt as usize..]);
        }
    } else {
        out.push_str(&digits[..1]);
        if n > 1 {
            out.push('.');
            out.push_str(&digits[1..]);
        }
        out.push('e');
        out.push(if exp < 0 { '-' } else { '+' });
        let a = exp.unsigned_abs();
        if a < 10 {
            out.push('0');
        }
        out.push_str(&a.to_string());
    }
    out
}

fn write_str(out: &mut String, s: &str) {
    out.push('"');
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            '\u{08}' => out.push_str("\\b"),
            '\u{0c}' => out.push_str("\\f"),
            ' '..='~' => out.push(c),
            _ => {
                let mut buf = [0u16; 2];
                for unit in c.encode_utf16(&mut buf) {
                    out.push_str(&format!("\\u{:04x}", unit));
                }
            }
        }
    }
    out.push('"');
}

/// Python `==` between two decoded JSON values.
///
/// Numbers compare by value whatever their representation (`1 == 1.0`), booleans equal the
/// integers 0/1 (`True == 1`), containers compare element-wise, objects ignore key order.
pub fn py_eq(a: &Value, b: &Value) -> bool {
    match (a, b) {
        (Value::Null, Value::Null) => true,
        (Value::Bool(x), Value::Bool(y)) => x == y,
        (Value::Bool(x), Value::Number(n)) | (Value::Number(n), Value::Bool(x)) => {
            num_eq(n, &Number::from(*x as i64))
        }
        (Value::Number(x), Value::Number(y)) => num_eq(x, y),
        (Value::String(x), Value::String(y)) => x == y,
        (Value::Array(x), Value::Array(y)) => {
            x.len() == y.len() && x.iter().zip(y).all(|(p, q)| py_eq(p, q))
        }
        (Value::Object(x), Value::Object(y)) => {
            x.len() == y.len() && x.iter().all(|(k, v)| y.get(k).is_some_and(|w| py_eq(v, w)))
        }
        _ => false,
    }
}

/// `py_eq` on optional values, where `None` is Python's `None` (== JSON null).
pub fn py_eq_opt(a: Option<&Value>, b: Option<&Value>) -> bool {
    match (a, b) {
        (None | Some(Value::Null), None | Some(Value::Null)) => true,
        (Some(x), Some(y)) => py_eq(x, y),
        _ => false,
    }
}

fn num_eq(a: &Number, b: &Number) -> bool {
    match (a.as_i64(), b.as_i64()) {
        (Some(x), Some(y)) => return x == y,
        _ => {}
    }
    match (a.as_u64(), b.as_u64()) {
        (Some(x), Some(y)) => return x == y,
        _ => {}
    }
    match (a.as_f64(), b.as_f64()) {
        (Some(x), Some(y)) => x == y,
        _ => false,
    }
}

/// Parse JSON text the way Python's `json.loads` does for the values Panoptic stores.
///
/// Besides strict JSON this accepts the non-standard `NaN` / `Infinity` / `-Infinity`
/// tokens Python can write; they decode to `null` (a `serde_json::Value` has no NaN).
pub fn loads(text: &str) -> serde_json::Result<Value> {
    match serde_json::from_str(text) {
        Ok(v) => Ok(v),
        Err(e) => {
            if text.contains("NaN") || text.contains("Infinity") {
                let cleaned = text.replace("-Infinity", "null").replace("Infinity", "null").replace("NaN", "null");
                serde_json::from_str(&cleaned)
            } else {
                Err(e)
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn floats_match_cpython_repr() {
        let cases = [
            (0.1, "0.1"),
            (1.0, "1.0"),
            (100.0, "100.0"),
            (1e16, "1e+16"),
            (1e15, "1000000000000000.0"),
            (1e-5, "1e-05"),
            (0.0001, "0.0001"),
            (1.5e-7, "1.5e-07"),
            (123456789.0, "123456789.0"),
            (1.2345678901234568e17, "1.2345678901234568e+17"),
            (-2.5, "-2.5"),
            (-0.0, "-0.0"),
            (1.5e300, "1.5e+300"),
            (42.5, "42.5"),
            (3.14159, "3.14159"),
        ];
        for (f, want) in cases {
            assert_eq!(float_repr(f), want, "{f}");
        }
    }

    #[test]
    fn dumps_matches_python() {
        let v = json!({"a": [1, 2.5, null, true, "é\u{7f}"], "b": 1e16, "c": 1e-5, "d": 123456789.0});
        assert_eq!(
            dumps(&v),
            r#"{"a": [1, 2.5, null, true, "é\u007f"], "b": 1e+16, "c": 1e-05, "d": 123456789.0}"#
        );
        assert_eq!(dumps_compact(&json!([10, "abc"])), r#"[10,"abc"]"#);
        assert_eq!(dumps(&json!("𝄞\n\"\\")), r#""𝄞\n\"\\""#);
    }

    #[test]
    fn python_equality() {
        assert!(py_eq(&json!(1), &json!(1.0)));
        assert!(py_eq(&json!(true), &json!(1)));
        assert!(!py_eq(&json!("1"), &json!(1)));
        assert!(py_eq(&json!({"a": [1, 2]}), &json!({"a": [1.0, 2]})));
        assert!(py_eq_opt(None, Some(&Value::Null)));
    }
}
