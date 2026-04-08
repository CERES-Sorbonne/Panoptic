import json
from dataclasses import dataclass, field
from sqlite3 import Cursor
from typing import Any, Iterable, Tuple

import msgspec
from msgspec.structs import astuple


@dataclass
class Col:
    name: str
    sql_type: str
    primary_key: bool = False
    nullable: bool = True


@dataclass
class EntitySchema:
    table: str
    columns: list[Col]
    chunk_size: int = 900
    trackable: bool = True

    _pk_names: list[str] = field(init=False, repr=False)
    _upsert_sql: str = field(init=False, repr=False)
    _insert_revert_sql: str = field(init=False, repr=False)
    _delete_single_sql: str = field(init=False, repr=False)
    _get_revert_sql: str = field(init=False, repr=False)

    def __post_init__(self):
        self._pk_names = [c.name for c in self.columns if c.primary_key]
        self._upsert_sql = self._generate_upsert_sql()
        self._insert_revert_sql = self._generate_insert_revert_sql()
        self._get_revert_sql = f"SELECT * FROM {self.table}_reverts WHERE commit_id = ?"

        pk_where = " AND ".join([f"{name} = ?" for name in self._pk_names])
        self._delete_single_sql = f"DELETE FROM {self.table} WHERE {pk_where}"
        self._json_indices = [
            i for i, c in enumerate(self.columns)
            if c.sql_type == "JSON"
        ]

    def _to_params(self, obj: msgspec.Struct) -> list:
        row = list(astuple(obj))
        for i in self._json_indices:
            if row[i] is not None:
                row[i] = json.dumps(row[i])
        return row

    def create_table_sql(self) -> str:
        definitions = []
        is_composite_pk = len(self._pk_names) > 1
        for c in self.columns:
            null = "" if c.nullable else " NOT NULL"
            pk = " PRIMARY KEY" if (c.primary_key and not is_composite_pk) else ""
            definitions.append(f"    {c.name} {c.sql_type}{pk}{null}")
        if self.trackable:
            definitions.append("    commit_id INTEGER")
        if is_composite_pk:
            definitions.append(f"    PRIMARY KEY ({', '.join(self._pk_names)})")
        return f"CREATE TABLE IF NOT EXISTS {self.table} (\n" + ",\n".join(definitions) + "\n);"

    def create_revert_table_sql(self) -> str:
        definitions = [f"    {c.name} {c.sql_type}" for c in self.columns]
        definitions.append("    commit_id INTEGER NOT NULL")
        definitions.append("    revert_commit_id INTEGER NOT NULL")
        definitions.append("    operation TEXT NOT NULL")
        full_pk = ", ".join(self._pk_names + ["revert_commit_id"])
        sql = f"CREATE TABLE IF NOT EXISTS {self.table}_reverts (\n" + ",\n".join(
            definitions) + f",\n    PRIMARY KEY ({full_pk})\n);"
        index = f"CREATE INDEX IF NOT EXISTS idx_{self.table}_revert_commit ON {self.table}_reverts (revert_commit_id);"
        return f"{sql}\n{index}"

    def _generate_upsert_sql(self) -> str:
        col_names = [c.name for c in self.columns]
        if self.trackable:
            col_names = col_names + ["commit_id"]
        cols = ", ".join(col_names)
        params = ", ".join("?" * len(col_names))
        return f"INSERT OR REPLACE INTO {self.table} ({cols}) VALUES ({params})"

    def _generate_insert_revert_sql(self) -> str:
        col_names = [c.name for c in self.columns] + ["commit_id", "revert_commit_id", "operation"]
        cols = ", ".join(col_names)
        params = ", ".join("?" * len(col_names))
        return f"INSERT INTO {self.table}_reverts ({cols}) VALUES ({params})"

    def build_get_sql(self, **filters) -> Tuple[str, tuple]:
        if not filters:
            return f"SELECT * FROM {self.table}", ()
        where_clauses, params = [], []
        for key, value in filters.items():
            if isinstance(value, (list, tuple)):
                placeholders = ", ".join(["?"] * len(value))
                where_clauses.append(f"{key} IN ({placeholders})")
                params.extend(value)
            else:
                where_clauses.append(f"{key} = ?")
                params.append(value)
        return f"SELECT * FROM {self.table} WHERE {' AND '.join(where_clauses)}", tuple(params)

    def build_bulk_upsert_sql(self, row_count: int) -> str:
        col_names = [c.name for c in self.columns]
        if self.trackable:
            col_names = col_names + ["commit_id"]
        row_placeholders = "(" + ", ".join(["?"] * len(col_names)) + ")"
        return f"INSERT OR REPLACE INTO {self.table} ({', '.join(col_names)}) VALUES {', '.join([row_placeholders] * row_count)}"

    def build_bulk_revert_sql(self, row_count: int) -> str:
        col_names = [c.name for c in self.columns] + ["commit_id", "revert_commit_id", "operation"]
        row_placeholders = "(" + ", ".join(["?"] * len(col_names)) + ")"
        return f"INSERT INTO {self.table}_reverts ({', '.join(col_names)}) VALUES {', '.join([row_placeholders] * row_count)}"

    def get(self, tx: Cursor, **filters) -> list[tuple]:
        sql, params = self.build_get_sql(**filters)
        return tx.execute(sql, params).fetchall()

    def get_revert_operations(self, tx: Cursor, commit_id: int) -> list[tuple]:
        return tx.execute(self._get_revert_sql, (commit_id,)).fetchall()

    def upserts(self, tx: Cursor, objs: Iterable[msgspec.Struct] | msgspec.Struct, commit_id: int = None):
        if self.trackable and commit_id is None:
            raise ValueError('Cant have no commit_id for trackable entities')
        if isinstance(objs, msgspec.Struct):
            data = [objs]
        else:
            data = list(objs)
        if not data:
            raise ValueError('objs is None')
        if self.trackable:
            for o in objs:
                o.commit_id = commit_id
        v_per_row = len(self.columns) + (1 if self.trackable else 0)
        c_size = self.chunk_size // v_per_row
        for i in range(0, len(data), c_size):
            chunk = data[i:i + c_size]
            params = []
            for o in chunk:
                params.extend(self._to_params(o))
            tx.execute(self.build_bulk_upsert_sql(len(chunk)), params)

    def insert_revert_operations(self, tx: Cursor, ops: Iterable[Tuple[msgspec.Struct, str]], revert_commit_id: int):
        if self.trackable and revert_commit_id is None:
            raise ValueError('Cant have no revert_commit_id for trackable entities')

        data = list(ops)
        if not data:
            return

        v_per_row = len(self.columns) + 2  #  revert_commit_id + operation
        c_size = self.chunk_size // v_per_row

        for i in range(0, len(data), c_size):
            chunk = data[i:i + c_size]
            params = []
            for obj, operation in chunk:
                params.extend(self._to_params(obj))
                params.append(revert_commit_id)
                params.append(operation)

            sql = self.build_bulk_revert_sql(len(chunk))
            tx.execute(sql, params)

    def deletes(self, tx: Cursor, pk_list: Iterable[Any]):
        pks = list(pk_list)
        if not pks: return
        num_pks = len(self._pk_names)

        if num_pks == 1 and len(pks) <= self.chunk_size:
            sql = f"DELETE FROM {self.table} WHERE {self._pk_names[0]} IN ({', '.join(['?'] * len(pks))})"
            params = [p[0] if isinstance(p, tuple) else p for p in pks]
            tx.execute(sql, params)
            return

        tmp_name = f"_del_tmp_{self.table}"
        pk_cols_str = ", ".join(self._pk_names)
        tx.execute(f"CREATE TEMP TABLE IF NOT EXISTS {tmp_name} ({pk_cols_str})")

        params = [p if isinstance(p, tuple) else (p,) for p in pks]
        tx.executemany(f"INSERT INTO {tmp_name} VALUES ({', '.join(['?'] * num_pks)})", params)

        where = f"({pk_cols_str}) IN (SELECT {pk_cols_str} FROM {tmp_name})" if num_pks > 1 else f"{pk_cols_str} IN (SELECT {pk_cols_str} FROM {tmp_name})"
        tx.execute(f"DELETE FROM {self.table} WHERE {where}")
        tx.execute(f"DELETE FROM {tmp_name}")