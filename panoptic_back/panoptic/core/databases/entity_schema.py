"""
entity_schema.py
~~~~~~~~~~~~~~~~
Automatic SQL schema management derived from msgspec.Struct definitions.

Usage
-----
    class Instance(msgspec.Struct, array_like=True):
        id:        Annotated[int, PrimaryKey]
        file_id:   Optional[int]
        sha1:      Optional[str]
        commit_id: Optional[int] = None
        operation: Optional[int] = None

    schema = EntitySchema(Instance, table="instances")
    schema.upsert(tx, objs, commit_id=42, sequence=42)

Trackable detection
-------------------
A struct is trackable when it declares both:
    commit_id: Optional[int]
    operation: Optional[int]

`sequence` is NOT declared on the struct — it is a DB-only column written
by EntitySchema during upsert and used exclusively for get_since() queries.

Main table column layout (trackable)
-------------------------------------
    <data cols...>  commit_id  operation  sequence

Log table column layout
-----------------------
    <data cols...>  commit_id  operation

Filter API  (get / delete)
--------------------------
**filters accepts any mix of scalar and list values.

    scalar  →  col = ?
    list    →  col IN (...)

Multiple list filters are AND-ed. The largest list is chunked (iterated in
slices ≤ chunk_size vars). All smaller lists are emitted as a single IN
clause repeated per chunk iteration. Scalar filters are appended once per
chunk.
"""

from __future__ import annotations

import datetime
import json
from dataclasses import dataclass, field
from sqlite3 import Cursor
from typing import Any, Iterable, Optional, get_args, get_origin, get_type_hints
import types as _types
import typing as _typing

import msgspec
import msgspec.structs
import msgspec.json as msgjson
from msgspec.structs import replace

import numpy as np

# ---------------------------------------------------------------------------
# Public sentinel
# ---------------------------------------------------------------------------

class PrimaryKey:
    """Marker placed inside Annotated[T, PrimaryKey] to designate PK columns."""


# ---------------------------------------------------------------------------
# Operation constants
# ---------------------------------------------------------------------------

OP_CREATE = 1
OP_UPDATE = 0
OP_DELETE = -1
OP_DIFF   = 2  # PropertyValueSchema only: apply tag diff instead of replace

# ---------------------------------------------------------------------------
# Limits
# ---------------------------------------------------------------------------

_SQLITE_MAX_VARS = 900

# ---------------------------------------------------------------------------
# Tracking field names on the struct (sequence is intentionally absent)
# ---------------------------------------------------------------------------

_TRACKING_FIELDS = frozenset({"commit_id", "operation"})

# ---------------------------------------------------------------------------
# Type mapping
# ---------------------------------------------------------------------------

_PY_TO_SQL: dict[Any, str] = {
    int:               "INTEGER",
    str:               "TEXT",
    float:             "REAL",
    bool:              "INTEGER",
    bytes:             "BLOB",
    datetime.datetime: "TIMESTAMP",
    np.ndarray:        "ARRAY",
}

_UNION_ORIGINS = {
    _typing.Union,
    getattr(_types, "UnionType", None),
}


def _unwrap_optional(py_type: Any) -> Any:
    origin = get_origin(py_type)
    if origin in _UNION_ORIGINS:
        non_none = [a for a in get_args(py_type) if a is not type(None)]
        return non_none[0] if non_none else py_type
    return py_type


def _is_optional(py_type: Any) -> bool:
    origin = get_origin(py_type)
    return origin in _UNION_ORIGINS and type(None) in get_args(py_type)


def _sql_type(py_type: Any) -> str:
    unwrapped = _unwrap_optional(py_type)
    origin    = get_origin(unwrapped)

    if unwrapped is Any:
        return "JSON"
    if origin in (list, dict):
        return "JSON"
    if origin is not None:
        return "JSON"
    if unwrapped in _PY_TO_SQL:
        return _PY_TO_SQL[unwrapped]

    raise TypeError(f"Cannot map Python type {py_type!r} to an SQL type")


# ---------------------------------------------------------------------------
# Column descriptor
# ---------------------------------------------------------------------------

@dataclass
class Col:
    name:        str
    sql_type:    str
    primary_key: bool = False
    nullable:    bool = True


# ---------------------------------------------------------------------------
# Introspection
# ---------------------------------------------------------------------------

def _introspect(struct_cls: type) -> tuple[list[Col], bool]:
    hints   = get_type_hints(struct_cls, include_extras=True)
    fields_ = msgspec.structs.fields(struct_cls)
    names   = {f.name for f in fields_}

    is_trackable = _TRACKING_FIELDS.issubset(names)

    cols: list[Col] = []
    for f in fields_:
        if f.name in _TRACKING_FIELDS:
            continue

        hint  = hints[f.name]
        is_pk = False

        if get_origin(hint) is _typing.Annotated:
            base, *metadata = get_args(hint)
            is_pk = any(
                m is PrimaryKey or (isinstance(m, type) and issubclass(m, PrimaryKey))
                for m in metadata
            )
            hint = base

        cols.append(Col(
            name        = f.name,
            sql_type    = _sql_type(hint),
            primary_key = is_pk,
            nullable    = _is_optional(hint),
        ))

    return cols, is_trackable


# ---------------------------------------------------------------------------
# Filter helpers
# ---------------------------------------------------------------------------

@dataclass
class _ParsedFilters:
    big_col:     str  | None
    big_vals:    list | None
    small_lists: dict[str, list]
    scalars:     dict[str, Any]


def _parse_filters(filters: dict[str, Any]) -> _ParsedFilters:
    lists:   dict[str, list] = {}
    scalars: dict[str, Any]  = {}

    for col, val in filters.items():
        if isinstance(val, (list, tuple)):
            lists[col] = list(val)
        else:
            scalars[col] = val

    if not lists:
        return _ParsedFilters(None, None, {}, scalars)

    big_col  = max(lists, key=lambda k: len(lists[k]))
    big_vals = lists.pop(big_col)
    return _ParsedFilters(big_col, big_vals, lists, scalars)


def _fixed_clause(small_lists: dict[str, list], scalars: dict[str, Any]) -> tuple[str, list]:
    parts:  list[str] = []
    params: list      = []

    for col, vals in small_lists.items():
        ph = ", ".join(["?"] * len(vals))
        parts.append(f"{col} IN ({ph})")
        params.extend(vals)

    for col, val in scalars.items():
        parts.append(f"{col} = ?")
        params.append(val)

    return " AND ".join(parts), params


# ---------------------------------------------------------------------------
# EntitySchema
# ---------------------------------------------------------------------------

T = _typing.TypeVar("T", bound=msgspec.Struct)


@dataclass
class EntitySchema(_typing.Generic[T]):
    """SQL schema manager auto-derived from a msgspec.Struct subclass."""

    struct_cls: type[T]
    table:      str
    chunk_size: int = _SQLITE_MAX_VARS

    columns:   list[Col] = field(init=False, repr=False)
    trackable: bool      = field(init=False, repr=False)
    _pk_names: list[str] = field(init=False, repr=False)
    _json_idx: list[int] = field(init=False, repr=False)
    _decode_strip: int   = field(init=False, repr=False)

    _log_by_commit_sql: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.columns, self.trackable = _introspect(self.struct_cls)
        self._pk_names    = [c.name for c in self.columns if c.primary_key]
        self._json_idx    = [i for i, c in enumerate(self.columns) if c.sql_type == "JSON"]
        self._array_idx = [i for i, c in enumerate(self.columns) if c.sql_type == "ARRAY"]
        self._decode_strip = 1 if self.trackable else 0

        if not self._pk_names:
            raise ValueError(
                f"Struct {self.struct_cls.__name__!r} has no PrimaryKey-annotated fields"
            )

        if self.trackable:
            self._log_by_commit_sql = (
                f"SELECT * FROM {self.table}_log WHERE commit_id = ?"
            )

        self._build_decoders()

    # ------------------------------------------------------------------
    # DDL
    # ------------------------------------------------------------------

    def create_table_sql(self) -> str:
        definitions: list[str] = []
        composite_pk = len(self._pk_names) > 1

        for c in self.columns:
            null = "" if c.nullable else " NOT NULL"
            pk   = " PRIMARY KEY" if (c.primary_key and not composite_pk) else ""
            definitions.append(f"    {c.name} {c.sql_type}{pk}{null}")

        if self.trackable:
            definitions.append("    commit_id INTEGER")
            definitions.append("    operation INTEGER")
            definitions.append("    sequence  INTEGER")

        if composite_pk:
            definitions.append(f"    PRIMARY KEY ({', '.join(self._pk_names)})")

        idx_seq = ""
        if self.trackable:
            idx_seq = (
                f"CREATE INDEX IF NOT EXISTS idx_{self.table}_sequence"
                f" ON {self.table} (sequence);"
            )
        return (
            f"CREATE TABLE IF NOT EXISTS {self.table} (\n"
            + ",\n".join(definitions)
            + "\n);\n"
            + idx_seq
        )

    def create_log_table_sql(self) -> str:
        if not self.trackable:
            raise ValueError(f"Table {self.table!r} is not trackable")

        definitions = [f"    {c.name} {c.sql_type}" for c in self.columns]
        definitions.append("    commit_id  INTEGER NOT NULL")
        definitions.append("    operation  INTEGER NOT NULL")

        full_pk   = ", ".join(self._pk_names + ["commit_id"])
        table_sql = (
            f"CREATE TABLE IF NOT EXISTS {self.table}_log (\n"
            + ",\n".join(definitions)
            + f",\n    PRIMARY KEY ({full_pk})\n);"
        )
        pk_cols    = ", ".join(self._pk_names)
        idx_commit = (
            f"CREATE INDEX IF NOT EXISTS idx_{self.table}_log_commit"
            f" ON {self.table}_log (commit_id);"
        )
        idx_entity = (
            f"CREATE INDEX IF NOT EXISTS idx_{self.table}_log_entity"
            f" ON {self.table}_log ({pk_cols}, commit_id);"
        )
        return f"{table_sql}\n{idx_commit}\n{idx_entity}"

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def _to_row(self, obj: T) -> list:
        t   = msgspec.structs.astuple(obj)
        row = list(t[: len(self.columns)])
        for i in self._json_idx:
            if row[i] is not None:
                row[i] = json.dumps(row[i])
        for i in self._array_idx:
            if row[i] is not None:
                row[i] = row[i].tobytes()
        return row

    def _to_row_trackable(self, obj: T, sequence: int) -> list:
        t   = msgspec.structs.astuple(obj)
        row = list(t[: len(self.columns) + 2])
        for i in self._json_idx:
            if row[i] is not None:
                row[i] = json.dumps(row[i])
        for i in self._array_idx:
            if row[i] is not None:
                row[i] = row[i].tobytes()
        row.append(sequence)
        return row

    def _decode_row(self, row: tuple) -> T:
        return self._row_decoder(row)

    def _decode_log_row(self, row: tuple) -> T:
        return self._log_row_decoder(row)

    # ------------------------------------------------------------------
    # SQL builders
    # ------------------------------------------------------------------

    def _build_upsert_sql(self, n: int) -> str:
        col_names = [c.name for c in self.columns]
        if self.trackable:
            col_names += ["commit_id", "operation", "sequence"]
        ph = "(" + ", ".join(["?"] * len(col_names)) + ")"
        return (
            f"INSERT OR REPLACE INTO {self.table} ({', '.join(col_names)})"
            f" VALUES {', '.join([ph] * n)}"
        )

    def _build_log_sql(self, n: int) -> str:
        col_names = [c.name for c in self.columns] + ["commit_id", "operation"]
        ph = "(" + ", ".join(["?"] * len(col_names)) + ")"
        return (
            f"INSERT INTO {self.table}_log ({', '.join(col_names)})"
            f" VALUES {', '.join([ph] * n)}"
        )

    def _build_decoders(self):
        json_idx = self._json_idx
        array_idx = self._array_idx
        struct_cls = self.struct_cls
        strip_count = self._decode_strip

        def _run_decode(row: tuple, strip: bool) -> T:
            if strip and strip_count:
                row = row[:-strip_count]

            if not json_idx and not array_idx:
                return msgspec.convert(row, struct_cls)

            data = list(row)
            for i in json_idx:
                val = data[i]
                if val is not None:
                    data[i] = msgjson.decode(val) if isinstance(val, (str, bytes)) else val
            for i in array_idx:
                val = data[i]
                if val is not None:
                    data[i] = np.frombuffer(val, dtype=np.float32)  # ← bytes → np.ndarray
            return msgspec.convert(data, struct_cls)

        self._row_decoder = lambda r: _run_decode(r, strip=True)
        self._log_row_decoder = lambda r: _run_decode(r, strip=False)

    # ------------------------------------------------------------------
    # Core chunked execution engine
    # ------------------------------------------------------------------

    def _execute_chunked(
        self,
        tx:     Cursor,
        action: str,
        pf:     _ParsedFilters,
    ) -> list[tuple]:
        fixed_clause, fixed_params = _fixed_clause(pf.small_lists, pf.scalars)
        fixed_var_count = len(fixed_params)

        if pf.big_col is None:
            sql  = f"{action} FROM {self.table}"
            if fixed_clause:
                sql += f" WHERE {fixed_clause}"
            return tx.execute(sql, fixed_params).fetchall()

        vars_for_big = self.chunk_size - fixed_var_count
        if vars_for_big < 1:
            raise ValueError(
                f"Fixed filter variables ({fixed_var_count}) leave no room for "
                f"chunked IN on {pf.big_col!r}. Reduce the size of other list filters."
            )

        results: list[tuple] = []
        for i in range(0, len(pf.big_vals), vars_for_big):
            chunk = pf.big_vals[i : i + vars_for_big]
            in_ph = ", ".join(["?"] * len(chunk))
            parts = [f"{pf.big_col} IN ({in_ph})"]
            if fixed_clause:
                parts.append(fixed_clause)
            sql    = f"{action} FROM {self.table} WHERE {' AND '.join(parts)}"
            params = chunk + fixed_params
            results.extend(tx.execute(sql, params).fetchall())
        return results

    # ------------------------------------------------------------------
    # Log table PK query (private)
    # ------------------------------------------------------------------

    def _get_log_by_pks(self, tx: Cursor, pk_list: list[Any]) -> list[T]:
        """Fetch all log rows for the given PKs, ordered by commit_id."""
        if not pk_list:
            return []

        log_table      = f"{self.table}_log"
        pk_cols        = ", ".join(self._pk_names)
        num_pks        = len(self._pk_names)
        order_by       = f" ORDER BY {pk_cols}, commit_id"
        chunk_size     = max(1, self.chunk_size // num_pks)

        results: list[tuple] = []

        if num_pks == 1:
            col = self._pk_names[0]
            for i in range(0, len(pk_list), chunk_size):
                chunk = pk_list[i : i + chunk_size]
                in_ph = ", ".join(["?"] * len(chunk))
                sql   = f"SELECT * FROM {log_table} WHERE {col} IN ({in_ph}){order_by}"
                results.extend(tx.execute(sql, chunk).fetchall())
        else:
            placeholders = ", ".join([f"({','.join(['?'] * num_pks)})"] * chunk_size)
            sql_tpl = (
                f"SELECT * FROM {log_table}"
                f" WHERE ({pk_cols}) IN (VALUES {placeholders}){order_by}"
            )
            for i in range(0, len(pk_list), chunk_size):
                chunk = pk_list[i : i + chunk_size]
                if len(chunk) < chunk_size:
                    ph  = ", ".join([f"({','.join(['?'] * num_pks)})"] * len(chunk))
                    sql = (
                        f"SELECT * FROM {log_table}"
                        f" WHERE ({pk_cols}) IN (VALUES {ph}){order_by}"
                    )
                else:
                    sql = sql_tpl
                params = [v for row in chunk for v in (row if isinstance(row, (tuple, list)) else [row])]
                results.extend(tx.execute(sql, params).fetchall())

        return [self._decode_log_row(r) for r in results]

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get(self, tx: Cursor, **filters) -> list[T]:
        pf   = _parse_filters(filters)
        rows = self._execute_chunked(tx, "SELECT *", pf)
        return [self._decode_row(r) for r in rows]

    def get_by_pk(self, tx: Cursor, pk_list: Iterable[Any]) -> list[T]:
        pks = list(pk_list)
        if not pks: return []

        num_pks_per_row = len(self._pk_names)
        chunk_size = 900 // num_pks_per_row

        results = []
        pk_cols = ", ".join(self._pk_names)
        placeholders = ", ".join([f"({','.join(['?'] * num_pks_per_row)})"] * chunk_size)
        sql = f"SELECT * FROM {self.table} WHERE ({pk_cols}) IN (VALUES {placeholders})"

        for i in range(0, len(pks) - chunk_size + 1, chunk_size):
            chunk = pks[i: i + chunk_size]
            params = [item for row in chunk for item in (row if isinstance(row, (tuple, list)) else [row])]
            results.extend(tx.execute(sql, params).fetchall())

        remainder = pks[(len(pks) // chunk_size) * chunk_size:]
        if remainder:
            tail_placeholders = ", ".join([f"({','.join(['?'] * num_pks_per_row)})"] * len(remainder))
            tail_sql = f"SELECT * FROM {self.table} WHERE ({pk_cols}) IN (VALUES {tail_placeholders})"
            params = [item for row in remainder for item in (row if isinstance(row, (tuple, list)) else [row])]
            results.extend(tx.execute(tail_sql, params).fetchall())

        return [self._decode_row(r) for r in results]

    def extract_pks(self, objs: Iterable[T]) -> list[Any]:
        names   = self._pk_names
        num_pks = len(names)

        if num_pks == 0:
            raise ValueError(f"Schema for {self.table} has no primary keys defined.")

        if num_pks == 1:
            pk = names[0]
            return [getattr(obj, pk) for obj in objs]

        return [tuple(getattr(obj, name) for name in names) for obj in objs]

    def list_to_index(self, objs: Iterable[T]) -> dict[Any, T]:
        names   = self._pk_names
        num_pks = len(names)

        if num_pks == 0:
            raise ValueError(f"Schema for {self.table} has no primary keys defined.")

        if num_pks == 1:
            pk = names[0]
            return {getattr(obj, pk): obj for obj in objs}

        return {
            tuple(getattr(obj, name) for name in names): obj
            for obj in objs
        }

    def get_current(self, tx: Cursor, objs: list[T]):
        pk_list = self.extract_pks(objs)
        db_objs = self.get_by_pk_index(tx, pk_list)
        return db_objs

    def get_index(self, tx: Cursor, **filters) -> dict[Any, T]:
        objs = self.get(tx, **filters)
        if len(self._pk_names) == 1:
            pk = self._pk_names[0]
            return {getattr(obj, pk): obj for obj in objs}
        return {
            tuple(getattr(obj, pk) for pk in self._pk_names): obj
            for obj in objs
        }

    def get_by_pk_index(self, tx: Cursor, pk_list: Iterable[Any]) -> dict[Any, T]:
        objs = self.get_by_pk(tx, pk_list)
        if len(self._pk_names) == 1:
            pk = self._pk_names[0]
            return {getattr(obj, pk): obj for obj in objs}
        return {
            tuple(getattr(obj, pk) for pk in self._pk_names): obj
            for obj in objs
        }

    def get_since(self, tx: Cursor, sequence: int) -> list[T]:
        if not self.trackable:
            raise ValueError(f"Table {self.table!r} is not trackable")
        rows = tx.execute(
            f"SELECT * FROM {self.table} WHERE sequence > ?", (sequence,)
        ).fetchall()
        return [self._decode_row(r) for r in rows]

    def get_log(self, tx: Cursor, commit_id: int) -> list[T]:
        if not self.trackable:
            raise ValueError(f"Table {self.table!r} is not trackable")
        rows = tx.execute(self._log_by_commit_sql, (commit_id,)).fetchall()
        return [self._decode_log_row(r) for r in rows]

    def get_all_pk(self, tx: Cursor, **filters) -> list[Any]:
        if not self.trackable:
            raise ValueError(f"Table {self.table!r} is not trackable")

        pk_cols   = ", ".join(self._pk_names)
        log_table = f"{self.table}_log"
        select    = f"SELECT DISTINCT {pk_cols}"

        pf                         = _parse_filters(filters)
        fixed_clause, fixed_params = _fixed_clause(pf.small_lists, pf.scalars)

        if pf.big_col is None:
            sql  = f"{select} FROM {log_table}"
            if fixed_clause:
                sql += f" WHERE {fixed_clause}"
            rows = tx.execute(sql, fixed_params).fetchall()
        else:
            vars_for_big = self.chunk_size - len(fixed_params)
            if vars_for_big < 1:
                raise ValueError(
                    f"Fixed filter variables ({len(fixed_params)}) leave no room for "
                    f"chunked IN on {pf.big_col!r}."
                )
            seen: dict[Any, None] = {}
            for i in range(0, len(pf.big_vals), vars_for_big):
                chunk = pf.big_vals[i : i + vars_for_big]
                in_ph = ", ".join(["?"] * len(chunk))
                parts = [f"{pf.big_col} IN ({in_ph})"]
                if fixed_clause:
                    parts.append(fixed_clause)
                sql    = f"{select} FROM {log_table} WHERE {' AND '.join(parts)}"
                params = chunk + fixed_params
                for row in tx.execute(sql, params).fetchall():
                    seen[row] = None
            rows = list(seen)

        if len(self._pk_names) == 1:
            return [row[0] for row in rows]
        return list(rows)

    def get_latest_logs(self, tx: Cursor, **filters) -> list[T]:
        if not self.trackable:
            raise ValueError(f"Table {self.table!r} is not trackable")

        pk_cols   = ", ".join(self._pk_names)
        log_table = f"{self.table}_log"
        select    = (
            f"SELECT l.* FROM {log_table} l "
            f"INNER JOIN ("
            f"SELECT {pk_cols}, MAX(commit_id) AS max_commit FROM {log_table}"
        )

        pf                         = _parse_filters(filters)
        fixed_clause, fixed_params = _fixed_clause(pf.small_lists, pf.scalars)

        def _build_sql(where: str) -> str:
            inner = select
            if where:
                inner += f" WHERE {where}"
            inner += f" GROUP BY {pk_cols}) m"
            pk_join = " AND ".join(f"l.{c} = m.{c}" for c in self._pk_names)
            return inner + f" ON {pk_join} AND l.commit_id = m.max_commit"

        if pf.big_col is None:
            sql  = _build_sql(fixed_clause)
            rows = tx.execute(sql, fixed_params + fixed_params).fetchall()
        else:
            vars_for_big = self.chunk_size - len(fixed_params)
            if vars_for_big < 1:
                raise ValueError(
                    f"Fixed filter variables ({len(fixed_params)}) leave no room for "
                    f"chunked IN on {pf.big_col!r}."
                )
            seen: dict[Any, None] = {}
            for i in range(0, len(pf.big_vals), vars_for_big):
                chunk  = pf.big_vals[i : i + vars_for_big]
                in_ph  = ", ".join(["?"] * len(chunk))
                parts  = [f"{pf.big_col} IN ({in_ph})"]
                if fixed_clause:
                    parts.append(fixed_clause)
                where        = " AND ".join(parts)
                sql          = _build_sql(where)
                chunk_params = chunk + fixed_params
                for row in tx.execute(sql, chunk_params).fetchall():
                    seen[row] = None
            rows = list(seen)

        return [self._decode_log_row(r) for r in rows]

    # ------------------------------------------------------------------
    # Write — current-state table
    # ------------------------------------------------------------------

    def upsert(
        self,
        tx:        Cursor,
        objs:      Iterable[T] | T,
        sequence:  int = None,
    ) -> None:
        data = [objs] if isinstance(objs, msgspec.Struct) else list(objs)
        if not data:
            return

        if self.trackable:
            vars_per_row = len(self.columns) + 3
            chunk_rows   = max(1, self.chunk_size // vars_per_row)
            for i in range(0, len(data), chunk_rows):
                chunk  = data[i : i + chunk_rows]
                params = []
                for obj in chunk:
                    params.extend(self._to_row_trackable(obj, sequence))
                tx.execute(self._build_upsert_sql(len(chunk)), params)
        else:
            vars_per_row = len(self.columns)
            chunk_rows   = max(1, self.chunk_size // vars_per_row)
            for i in range(0, len(data), chunk_rows):
                chunk  = data[i : i + chunk_rows]
                params = []
                for obj in chunk:
                    params.extend(self._to_row(obj))
                tx.execute(self._build_upsert_sql(len(chunk)), params)

    # ------------------------------------------------------------------
    # Write — log table
    # ------------------------------------------------------------------

    def append_log(self, tx: Cursor, objs: Iterable[T], commit_id: int) -> None:
        if not self.trackable:
            raise ValueError(f"Table {self.table!r} is not trackable")

        data = list(objs)
        if not data:
            return

        for obj in data:
            if obj.operation is None:
                raise ValueError(f"operation must be set before appending to log: {obj!r}")

        vars_per_row = len(self.columns) + 2
        chunk_rows   = max(1, self.chunk_size // vars_per_row)

        for i in range(0, len(data), chunk_rows):
            chunk  = data[i : i + chunk_rows]
            params = []
            for obj in chunk:
                params.extend(self._to_row(obj))
                params.append(commit_id)
                params.append(obj.operation)
            tx.execute(self._build_log_sql(len(chunk)), params)

    # ------------------------------------------------------------------
    # Delete — current-state table
    # ------------------------------------------------------------------

    def delete(self, tx: Cursor, **filters) -> None:
        if not filters:
            raise ValueError("delete() requires at least one filter")
        pf = _parse_filters(filters)
        self._execute_chunked(tx, "DELETE", pf)

    def delete_by_pk(self, tx: Cursor, pk_list: Iterable[Any]) -> None:
        pks = list(pk_list)
        if not pks:
            return

        num_pk = len(self._pk_names)

        if num_pk == 1:
            col = self._pk_names[0]
            for i in range(0, len(pks), self.chunk_size):
                chunk = pks[i : i + self.chunk_size]
                in_ph = ", ".join(["?"] * len(chunk))
                tx.execute(f"DELETE FROM {self.table} WHERE {col} IN ({in_ph})", chunk)
        else:
            pk_cols    = ", ".join(self._pk_names)
            tmp        = f"_del_tmp_{self.table}"
            ph         = ", ".join(["?"] * num_pk)
            chunk_rows = max(1, self.chunk_size // num_pk)

            tx.execute(f"CREATE TEMP TABLE IF NOT EXISTS {tmp} ({pk_cols})")
            rows = [p if isinstance(p, tuple) else (p,) for p in pks]
            for i in range(0, len(rows), chunk_rows):
                tx.executemany(f"INSERT INTO {tmp} VALUES ({ph})", rows[i : i + chunk_rows])

            where = f"({pk_cols}) IN (SELECT {pk_cols} FROM {tmp})"
            tx.execute(f"DELETE FROM {self.table} WHERE {where}")
            tx.execute(f"DELETE FROM {tmp}")

    # ------------------------------------------------------------------
    # Domain operations
    # ------------------------------------------------------------------

    def set_to_delete(self, objs: list[T], commit_id: int) -> None:
        for obj in objs:
            obj.commit_id = commit_id
            obj.operation = OP_DELETE

    @staticmethod
    def merge_logs(objs: list[msgspec.Struct]) -> msgspec.Struct | None:
        current: msgspec.Struct | None = None
        for obj in objs:
            if obj is None:
                continue
            op = getattr(obj, "operation", None)

            if current is None:
                if op == OP_CREATE:
                    current = replace(obj, operation=OP_CREATE)
            else:
                if op == OP_DELETE:
                    current = replace(obj)
                else:
                    current = replace(obj, operation=OP_CREATE)
        return current

    def re_compute(
            self,
            tx: Cursor,
            pk_list: Any,
            sequence: int,
            disabled_commits: set[int]
    ) -> list[T]:
        """Replay log entries for the given PKs and upsert the merged state.

        For each PK, all valid log rows are fetched in commit_id order, folded via
        merge_logs, and the resulting objects are bulk-upserted into the
        current-state table. Commits present in disabled_commits are ignored.
        PKs whose log produces None (no CREATE ever seen) are silently skipped.

        Returns the list of upserted objects.
        """
        if not self.trackable:
            raise ValueError(f"Table {self.table!r} is not trackable")

        pks = list(pk_list) if not isinstance(pk_list, list) else pk_list
        if not pks:
            return []

        log_rows = self._get_log_by_pks(tx, pks)

        # Group by PK, preserving commit_id order (guaranteed by _get_log_by_pks)
        # and skipping any disabled commits.
        grouped: dict[Any, list[T]] = {}
        if len(self._pk_names) == 1:
            pk_attr = self._pk_names[0]
            for obj in log_rows:
                if obj.commit_id in disabled_commits:
                    continue
                key = getattr(obj, pk_attr)
                grouped.setdefault(key, []).append(obj)
        else:
            for obj in log_rows:
                if obj.commit_id in disabled_commits:
                    continue
                key = tuple(getattr(obj, name) for name in self._pk_names)
                grouped.setdefault(key, []).append(obj)

        merged: list[T] = []
        for entries in grouped.values():
            result = self.merge_logs(entries)
            if result is not None:
                merged.append(result)

        if merged:
            self.upsert(tx, merged, sequence=sequence)

        return merged


# ---------------------------------------------------------------------------
# PropertyValueSchema
# ---------------------------------------------------------------------------

def _apply_diff(current: list[int] | None, diff: list[int]) -> list[int]:
    working: set[int] = set(current) if current else set()
    for tag in diff:
        if tag < 0:
            working.discard(-tag)
        else:
            working.add(tag)
    return sorted(working)


@dataclass
class PropertyValueSchema(EntitySchema[T]):
    """EntitySchema specialised for property-value tables."""

    is_multi_tags: bool = False

    @staticmethod
    def merge_logs(objs: list[msgspec.Struct], is_multi_tags: bool = False) -> msgspec.Struct | None:
        filtered = [o for o in objs if o is not None]
        if not filtered:
            return None

        if not is_multi_tags:
            return msgspec.structs.replace(filtered[-1])

        accumulated: list[int] | None = None

        for obj in filtered:
            val = getattr(obj, "value", None)
            op  = getattr(obj, "operation", None)

            if val is None:
                accumulated = None
            elif op == OP_DIFF:
                accumulated = _apply_diff(accumulated, val)
            else:
                accumulated = list(val)

        final_val = accumulated if accumulated else None
        return msgspec.structs.replace(filtered[-1], value=final_val)

    def re_compute(
            self,
            tx: Cursor,
            pk_list: Any,
            sequence: int,
            disabled_commits: set[int],
            multi_tags_property_ids: set[int] | None = None,
    ) -> list[T]:
        """Replay log entries for the given PKs and upsert the merged state."""
        if not self.trackable:
            raise ValueError(f"Table {self.table!r} is not trackable")

        pks = list(pk_list) if not isinstance(pk_list, list) else pk_list
        if not pks:
            return []

        log_rows = self._get_log_by_pks(tx, pks)

        # Group only logs with valid commit_ids
        grouped: dict[Any, list[T]] = {}
        for obj in log_rows:
            if obj.commit_id in disabled_commits:
                continue

            if len(self._pk_names) == 1:
                key = getattr(obj, self._pk_names[0])
            else:
                key = tuple(getattr(obj, name) for name in self._pk_names)

            grouped.setdefault(key, []).append(obj)

        merged: list[T] = []

        for key, entries in grouped.items():
            # Assumption: property_id is the first PK field
            prop_id = key[0] if isinstance(key, tuple) else key

            is_multi_tag = (
                prop_id in multi_tags_property_ids
                if multi_tags_property_ids is not None
                else getattr(self, 'is_multi_tags', False)
            )

            if is_multi_tag:
                # Multi-tags: Merge all valid logs to calculate the final list state
                result = PropertyValueSchema.merge_logs(entries, is_multi_tags=True)
                if result is not None:
                    merged.append(result)
            else:
                # Standard property: The final state is simply the log with the highest valid commit_id
                latest_log = max(entries, key=lambda e: e.commit_id)
                merged.append(latest_log)

        if merged:
            self.upsert(tx, merged, sequence=sequence)

        return merged
