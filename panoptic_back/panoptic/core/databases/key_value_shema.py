# ---------------------------------------------------------------------------
# KeyValueSchema
# ---------------------------------------------------------------------------
import typing as _typing
import json
from dataclasses import dataclass, field
from sqlite3 import Cursor
from typing import Any

import msgspec

T = _typing.TypeVar("T", bound=msgspec.Struct)

@dataclass
class KeyValueSchema(_typing.Generic[T]):
    """
    Schema manager for a flat key-value SQLite table derived from a
    msgspec.Struct subclass.

    Table layout: key TEXT PRIMARY KEY, value JSON

    One row per field declared on the struct. Default values (if any) are
    seeded via ensure_keys(); missing fields fall back to NULL.

    Usage
    -----
        class MyCounters(msgspec.Struct):
            elem:   int
            others: int = 0

        schema = KeyValueSchema(MyCounters, table="my_counters")
        schema.ensure_keys(tx)          # seed missing rows (idempotent)

        counters = schema.get(tx)       # → MyCounters(elem=0, others=0)
        schema.set_key(tx, "elem", 42)
        schema.set(tx, MyCounters(elem=99, others=7))
        val = schema.get_key(tx, "elem")  # → 99
    """

    struct_cls: type[T]
    table:      str

    _fields: list[msgspec.structs.FieldInfo] = field(init=False, repr=False)
    _defaults: dict[str, Any]               = field(init=False, repr=False)
    _field_names: frozenset[str]            = field(init=False, repr=False)

    @property
    def trackable(self): return False

    def __post_init__(self) -> None:
        self._fields     = list(msgspec.structs.fields(self.struct_cls))
        self._field_names = frozenset(f.name for f in self._fields)
        self._defaults   = {}

        for f in self._fields:
            # msgspec uses a sentinel for "no default"; handle both
            # nodefault and factory defaults gracefully
            default = f.default
            if default is not msgspec.NODEFAULT:
                self._defaults[f.name] = default
            elif f.default_factory is not msgspec.NODEFAULT:  # type: ignore[misc]
                self._defaults[f.name] = f.default_factory()
            # else: no default → will be NULL

    # ------------------------------------------------------------------
    # DDL
    # ------------------------------------------------------------------

    def create_table_sql(self) -> str:
        return (
            f"CREATE TABLE IF NOT EXISTS {self.table} (\n"
            f"    key   TEXT PRIMARY KEY,\n"
            f"    value JSON\n"
            f");"
        )

    # ------------------------------------------------------------------
    # Seed / migration
    # ------------------------------------------------------------------

    def ensure_keys(self, tx: Cursor) -> None:
        """Insert a row for every struct field that doesn't already exist.

        Uses INSERT OR IGNORE so existing values are never overwritten.
        Safe to call on every connection open — fully idempotent.
        """
        for f in self._fields:
            default = self._defaults.get(f.name)
            value   = json.dumps(default) if default is not None else None
            tx.execute(
                f"INSERT OR IGNORE INTO {self.table} (key, value) VALUES (?, ?)",
                (f.name, value),
            )

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_key(self, tx: Cursor, key: str) -> Any:
        """Return the decoded value for a single key, or None if absent."""
        if key not in self._field_names:
            raise KeyError(f"{key!r} is not a field of {self.struct_cls.__name__!r}")
        row = tx.execute(
            f"SELECT value FROM {self.table} WHERE key = ?", (key,)
        ).fetchone()
        if row is None or row[0] is None:
            return None
        return json.loads(row[0])

    def get(self, tx: Cursor) -> T:
        """Return a fully-populated struct instance, seeding defaults first.

        Fields missing from the DB (or stored as NULL) fall back to the
        struct's own default; if there is none, the field is set to None.
        """
        self.ensure_keys(tx)
        rows = tx.execute(f"SELECT key, value FROM {self.table}").fetchall()
        row_map: dict[str, Any] = {}
        for k, v in rows:
            if k in self._field_names:
                row_map[k] = json.loads(v) if v is not None else None

        kwargs: dict[str, Any] = {}
        for f in self._fields:
            if f.name in row_map and row_map[f.name] is not None:
                kwargs[f.name] = row_map[f.name]
            elif f.name in self._defaults:
                kwargs[f.name] = self._defaults[f.name]
            else:
                kwargs[f.name] = None

        return msgspec.convert(kwargs, self.struct_cls)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def set_key(self, tx: Cursor, key: str, value: Any) -> None:
        """Upsert a single key."""
        if key not in self._field_names:
            raise KeyError(f"{key!r} is not a field of {self.struct_cls.__name__!r}")
        encoded = json.dumps(value) if value is not None else None
        tx.execute(
            f"INSERT INTO {self.table} (key, value) VALUES (?, ?)"
            f" ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, encoded),
        )

    def set(self, tx: Cursor, obj: T) -> None:
        """Upsert all fields from a struct instance."""
        if not isinstance(obj, self.struct_cls):
            raise TypeError(
                f"Expected {self.struct_cls.__name__!r}, got {type(obj).__name__!r}"
            )
        for f in self._fields:
            self.set_key(tx, f.name, getattr(obj, f.name))