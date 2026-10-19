"""Direct writers.

* :class:`DataWriter` — port of the reference ``DataWriter.apply_commit`` (data/data_writer.py +
  data/resolver.py): partial-diff ChangeOps appended to ``entity_log``, a ``commits`` row, one
  ``sequence`` value per commit, materialization of the touched result rows, mono-tag arity.
  It is the *opt-in* path: by default plugins send their data writes to the backend (``commit``
  RPC). After a direct commit the caller must send ``db.changed``.
* :class:`MediaWriter` — vectors, vector types and maps in media.db.
* :func:`allocate_ids` — the project.db id registry (offline use; connected plugins call the
  ``ids.allocate`` RPC).

Everything here only touches the logged entities of data.db and the plugin's own media rows:
structural tables, undo/redo toggles and compaction belong to the backend.
"""
from __future__ import annotations

import copy
import dataclasses
import datetime
import json
from typing import Any, Callable, Iterable

from .. import models as m
from . import schema as s
from .reader import get_by_pk, get_entities, select_rows

Allocator = Callable[[str, int], int]   # (kind, count) -> first id of a contiguous range


# ---------------------------------------------------------------------------
# id registry (project.db)
# ---------------------------------------------------------------------------

def allocate_ids(cur, kind: str, count: int = 1) -> int:
    """Reserve ``count`` consecutive ids of ``kind``; returns the first (ProjectDB.allocate).

    ``cur`` must be inside a write transaction on project.db.
    """
    if kind not in s.ID_REGISTRY_KEYS:
        raise ValueError(f"{kind!r} is not an id registry key")
    row = cur.execute("SELECT value FROM id_registry WHERE key = ?", (kind,)).fetchone()
    current = s.json_load(row[0]) if row and row[0] is not None else 1
    cur.execute("INSERT INTO id_registry (key, value) VALUES (?, ?)"
                " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (kind, json.dumps(current + count)))
    return current


# ---------------------------------------------------------------------------
# placeholder ids
# ---------------------------------------------------------------------------

def assign_placeholder_ids(commit: m.DataCommit, allocate: Allocator) -> tuple[m.DataCommit, dict]:
    """Replace negative ids of new properties / groups / tags by allocated ids and rewrite the
    references to them. Returns (new commit, {kind: {placeholder: id}}).

    A new property whose ``tag_list_id`` is None or equals its placeholder gets
    ``tag_list_id = id`` (what the reference ``add_property`` does).
    """
    commit = copy.deepcopy(commit)
    ids: dict[str, dict[int, int]] = {'properties': {}, 'property_groups': {}, 'tags': {}}

    def alloc(kind: str, rows: list):
        neg = sorted({r.id for r in rows if r.id is not None and r.id < 0}, reverse=True)
        if neg:
            first = allocate(kind, len(neg))
            for i, ph in enumerate(neg):
                ids[kind][ph] = first + i

    alloc('property_groups', commit.property_groups)
    alloc('properties', commit.properties)
    alloc('tags', commit.tags)
    pmap, gmap, tmap = ids['properties'], ids['property_groups'], ids['tags']

    for g in commit.property_groups:
        g.id = gmap.get(g.id, g.id)
    for p in commit.properties:
        placeholder = p.id
        p.id = pmap.get(p.id, p.id)
        if placeholder in pmap and (p.tag_list_id is None or p.tag_list_id == placeholder):
            p.tag_list_id = p.id
        elif p.tag_list_id is not None and p.tag_list_id < 0:
            p.tag_list_id = pmap.get(p.tag_list_id, p.tag_list_id)
        if p.property_group_id is not None and p.property_group_id < 0:
            p.property_group_id = gmap.get(p.property_group_id, p.property_group_id)
    for t in commit.tags:
        t.id = tmap.get(t.id, t.id)
        if t.list_id is not None and t.list_id < 0:
            t.list_id = pmap.get(t.list_id, t.list_id)
        if t.parents:
            t.parents = [tmap.get(x, x) for x in t.parents]
    for rows in (commit.instance_values, commit.sha1_values, commit.file_values):
        for v in rows:
            v.property_id = pmap.get(v.property_id, v.property_id)
            if isinstance(v.value, list) and tmap:
                v.value = [tmap.get(x, x) if isinstance(x, int) else x for x in v.value]

    for kind, rows in (('properties', commit.properties), ('property_groups', commit.property_groups),
                       ('tags', commit.tags)):
        if any(r.id is not None and r.id < 0 for r in rows):
            raise ValueError(f"unresolved placeholder id in {kind}")
    return commit, {k: v for k, v in ids.items() if v}


# ---------------------------------------------------------------------------
# resolver  (data/resolver.py)
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class ChangeOp:
    entity_type: str
    entity_key: str
    commit: int
    op: int
    changes: dict | None = None


def diff_changes(spec: s.EntitySpec, current, incoming) -> dict:
    changes: dict = {}
    for f in spec.data_fields:
        nv = getattr(incoming, f)
        if current is None:
            if nv is not None:
                changes[f] = nv
        elif nv != getattr(current, f):
            changes[f] = nv
    for f in spec.set_fields:
        new = set(getattr(incoming, f) or [])
        old = set(getattr(current, f) or []) if current is not None else set()
        add, rem = new - old, old - new
        if add or rem:
            changes[f] = {'add': sorted(add), 'remove': sorted(rem)}
    return changes


def resolve(spec: s.EntitySpec, key: str, ops: Iterable[ChangeOp]):
    """Fold enabled ops (ascending commit order) into a typed row, or None when not alive."""
    alive = False
    last_commit = None
    scalars: dict[str, Any] = {}
    sets: dict[str, dict[Any, bool]] = {f: {} for f in spec.set_fields}
    for op in ops:
        last_commit = op.commit
        if op.op == s.OP_DELETE:
            alive = False
            continue
        if op.op == s.OP_CREATE:
            alive = True
        elif not alive:
            continue
        for k, v in (op.changes or {}).items():
            if k in sets:
                for x in v.get('remove', ()):
                    sets[k][x] = False
                for x in v.get('add', ()):
                    sets[k][x] = True
            else:
                scalars[k] = v
    if not alive:
        return None
    fields: dict[str, Any] = dict(zip(spec.pk_fields, s.decode_key(key)))
    for f in spec.data_fields:
        if f in scalars:
            fields[f] = scalars[f]
    for f in spec.set_fields:
        fields[f] = sorted(k for k, present in sets[f].items() if present)
    fields['commit_id'] = last_commit
    fields['operation'] = s.OP_CREATE
    return spec.table.model(**fields)


# ---------------------------------------------------------------------------
# DataWriter  (data/data_writer.py, apply_commit path only)
# ---------------------------------------------------------------------------

class DataWriter:
    def __init__(self, write_tx):
        """``write_tx()`` returns a context manager yielding a cursor inside BEGIN IMMEDIATE on data.db."""
        self._write_tx = write_tx

    def apply_commit(self, source: str, data: m.DataCommit, group_id: int | None = None,
                     author: str | None = None) -> tuple[m.Commit | None, int | None]:
        """Returns (commit row or None when nothing changed, sequence used)."""
        with self._write_tx() as tx:
            commit_id = tx.execute("SELECT COALESCE(MAX(id), 0) FROM commits").fetchone()[0] + 1
            now = datetime.datetime.now()
            if group_id is None:
                group_id = commit_id
            ops = self._build_ops(tx, data, commit_id)
            if not ops:
                return None, None
            seq = self._next_sequence(tx)
            commit = m.Commit(id=commit_id, group_id=group_id, source=source, timestamp=now,
                              active=1, author=author, redoable=1)
            tx.execute(s.COMMITS.upsert_sql(1), s.COMMITS.encode(commit))
            tx.execute("UPDATE commits SET redoable = 0"
                       " WHERE active = 0 AND redoable = 1 AND author IS ?", (author,))
            self._append_ops(tx, ops, seq)
            self._materialize_many(tx, {(o.entity_type, o.entity_key) for o in ops}, seq)
            return commit, seq

    # -- ops ------------------------------------------------------------------------------
    def _build_ops(self, tx, data: m.DataCommit, commit_id: int) -> list[ChangeOp]:
        ops: dict[tuple, ChangeOp] = {}

        def add(op):
            if op is not None:
                ops[(op.entity_type, op.entity_key)] = op

        del_prop_ids: list[int] = []
        del_tag_ids: list[int] = []
        for g in data.property_groups:
            add(self._entity_op(tx, 'group', g, commit_id))
        for p in data.properties:
            if p.operation == s.OP_DELETE:
                del_prop_ids.append(p.id)
            add(self._entity_op(tx, 'property', p, commit_id))
        for t in data.tags:
            if t.operation == s.OP_DELETE:
                del_tag_ids.append(t.id)
            add(self._entity_op(tx, 'tag', t, commit_id))

        dtypes = self._dtype_map(tx, data)
        cells = [('instance_value', 'instance_tag_value', 'instance_id', v.instance_id, v.property_id, v.value)
                 for v in data.instance_values]
        cells += [('sha1_value', 'sha1_tag_value', 'sha1', v.sha1, v.property_id, v.value)
                  for v in data.sha1_values]
        cells += [('file_value', None, 'file_id', v.file_id, v.property_id, v.value) for v in data.file_values]
        cells = [(vt, tt if dtypes.get(pid) in s.TAG_DTYPES else None, af, a, pid, val)
                 for vt, tt, af, a, pid, val in cells]
        values, tags = self._current_cells(tx, cells)
        for vt, tt, af, anchor, pid, value in cells:
            if tt:
                self._tag_junction_ops(tt, (af, anchor), pid, value, tags.get((tt, anchor, pid), set()),
                                       commit_id, add)
            else:
                add(self._scalar_value_op(vt, pid, anchor, value, values.get((vt, pid, anchor)), commit_id))
        for op in self._cascade_delete_ops(tx, del_prop_ids, del_tag_ids, commit_id):
            add(op)
        return list(ops.values())

    def _entity_op(self, tx, entity_type: str, incoming, commit_id: int):
        spec = s.ENTITY_SPECS[entity_type]
        key = s.key_of(spec, incoming)
        if getattr(incoming, 'operation', None) == s.OP_DELETE:
            if self._alive_row(tx, spec, key) is None:
                return None
            return ChangeOp(entity_type, key, commit_id, s.OP_DELETE, None)
        current = self._alive_row(tx, spec, key)
        op = s.OP_CREATE if current is None else s.OP_UPDATE
        changes = diff_changes(spec, current, incoming)
        if op == s.OP_UPDATE and not changes:
            return None
        return ChangeOp(entity_type, key, commit_id, op, changes)

    def _current_cells(self, tx, cells: list[tuple]) -> tuple[dict, dict]:
        scalar_pks: dict[str, dict[tuple, None]] = {}
        tag_anchors: dict[tuple, dict[Any, None]] = {}
        for vt, tt, af, anchor, pid, _ in cells:
            if tt:
                tag_anchors.setdefault((tt, af, pid), {})[anchor] = None
            else:
                spec = s.ENTITY_SPECS[vt]
                pk = tuple(pid if f == 'property_id' else anchor for f in spec.pk_fields)
                scalar_pks.setdefault(vt, {})[pk] = None
        values: dict[tuple, Any] = {}
        for vt, pks in scalar_pks.items():
            spec = s.ENTITY_SPECS[vt]
            af = next(f for f in spec.pk_fields if f != 'property_id')
            for r in get_by_pk(tx, spec.table, list(pks)):
                if r.operation != s.OP_DELETE:
                    values[(vt, r.property_id, getattr(r, af))] = r
        tags: dict[tuple, set] = {}
        for (tt, af, pid), anchors in tag_anchors.items():
            rows = get_entities(tx, s.ENTITY_SPECS[tt].table, state=0, property_id=pid, **{af: list(anchors)})
            for r in rows:
                if r.operation == s.OP_CREATE:
                    tags.setdefault((tt, getattr(r, af), pid), set()).add(r.tag_id)
        return values, tags

    @staticmethod
    def _scalar_value_op(entity_type, property_id, anchor, value, current, commit_id):
        spec = s.ENTITY_SPECS[entity_type]
        key = s.encode_key(tuple(property_id if f == 'property_id' else anchor for f in spec.pk_fields))
        if current is not None and current.value == value:
            return None
        return ChangeOp(entity_type, key, commit_id, s.OP_CREATE, {'value': value})

    @staticmethod
    def _tag_junction_ops(tag_type, extra, property_id, value, existing_tags, commit_id, add):
        spec = s.ENTITY_SPECS[tag_type]
        af, av = extra
        new_tags = set(value or [])

        def key_for(tag_id):
            return s.encode_key(tuple(av if f == af else property_id if f == 'property_id' else tag_id
                                      for f in spec.pk_fields))

        for tag_id in existing_tags - new_tags:
            add(ChangeOp(tag_type, key_for(tag_id), commit_id, s.OP_DELETE, None))
        for tag_id in new_tags - existing_tags:
            add(ChangeOp(tag_type, key_for(tag_id), commit_id, s.OP_CREATE, None))

    def _cascade_delete_ops(self, tx, prop_ids, tag_ids, commit_id):
        out: list[ChangeOp] = []
        tag_ids = list(tag_ids)
        if prop_ids:
            props = {p.id: p for p in get_entities(tx, s.PROPERTIES, id=prop_ids)}
            tag_prop_ids = [pid for pid, p in props.items() if p.dtype in s.TAG_DTYPES]
            non_tag_ids = [pid for pid, p in props.items() if p.dtype not in s.TAG_DTYPES]
            list_ids = [props[pid].tag_list_id for pid in tag_prop_ids if props[pid].tag_list_id is not None]
            if non_tag_ids:
                out += self._delete_ops_for(tx, 'instance_value', property_id=non_tag_ids)
                out += self._delete_ops_for(tx, 'sha1_value', property_id=non_tag_ids)
                out += self._delete_ops_for(tx, 'file_value', property_id=non_tag_ids)
            if tag_prop_ids:
                out += self._delete_ops_for(tx, 'instance_tag_value', property_id=tag_prop_ids)
                out += self._delete_ops_for(tx, 'sha1_tag_value', property_id=tag_prop_ids)
            if list_ids:
                for t in get_entities(tx, s.TAGS, list_id=list_ids):
                    out.append(ChangeOp('tag', s.encode_key((t.id,)), commit_id, s.OP_DELETE, None))
                    tag_ids.append(t.id)
        if tag_ids:
            out += self._delete_ops_for(tx, 'instance_tag_value', tag_id=tag_ids)
            out += self._delete_ops_for(tx, 'sha1_tag_value', tag_id=tag_ids)
        for op in out:
            op.commit = commit_id
        return out

    @staticmethod
    def _delete_ops_for(tx, entity_type, **filters):
        spec = s.ENTITY_SPECS[entity_type]
        return [ChangeOp(entity_type, s.key_of(spec, r), 0, s.OP_DELETE, None)
                for r in get_entities(tx, spec.table, **filters)]

    @staticmethod
    def _dtype_map(tx, data: m.DataCommit) -> dict[int, str]:
        p_ids = {v.property_id for v in data.instance_values}
        p_ids |= {v.property_id for v in data.sha1_values}
        p_ids |= {v.property_id for v in data.file_values}
        result: dict[int, str] = {}
        if p_ids:
            result = {p.id: p.dtype for p in get_entities(tx, s.PROPERTIES, id=list(p_ids))}
        for p in data.properties:
            if p.dtype is not None:
                result[p.id] = p.dtype
        return result

    # -- log + materialization ------------------------------------------------------------
    @staticmethod
    def _append_ops(tx, ops: list[ChangeOp], sequence: int) -> None:
        tx.executemany(
            "INSERT OR REPLACE INTO entity_log"
            " (entity_type, entity_key, commit_id, op, changes, sequence) VALUES (?,?,?,?,?,?)",
            [(o.entity_type, o.entity_key, o.commit, o.op,
              json.dumps(o.changes) if o.changes is not None else None, sequence) for o in ops])

    @staticmethod
    def _enabled_ops(tx, entity_type: str, key: str) -> list[ChangeOp]:
        rows = tx.execute(
            "SELECT el.op, el.changes, el.commit_id FROM entity_log el"
            " LEFT JOIN commits c ON c.id = el.commit_id"
            " WHERE el.entity_type = ? AND el.entity_key = ?"
            " AND (el.commit_id = 0 OR c.active = 1) ORDER BY el.commit_id", (entity_type, key)).fetchall()
        return [ChangeOp(entity_type, key, r[2], r[0], json.loads(r[1]) if r[1] is not None else None)
                for r in rows]

    @staticmethod
    def _enabled_ops_many(tx, entity_type: str, keys: list[str]) -> dict[str, list[ChangeOp]]:
        out: dict[str, list[ChangeOp]] = {}
        for chunk in s.chunks(keys):
            sql = ("SELECT el.entity_key, el.op, el.changes, el.commit_id FROM entity_log el"
                   " LEFT JOIN commits c ON c.id = el.commit_id"
                   f" WHERE el.entity_type = ? AND el.entity_key IN ({', '.join(['?'] * len(chunk))})"
                   " AND (el.commit_id = 0 OR c.active = 1) ORDER BY el.commit_id")
            for key, op, changes, cid in tx.execute(sql, [entity_type, *chunk]).fetchall():
                out.setdefault(key, []).append(
                    ChangeOp(entity_type, key, cid, op, json.loads(changes) if changes is not None else None))
        return out

    @staticmethod
    def _pk_arg(spec: s.EntitySpec, keys: list[str]) -> list:
        pks = [s.decode_key(k) for k in keys]
        return [pk[0] for pk in pks] if len(spec.pk_fields) == 1 else [tuple(pk) for pk in pks]

    def _alive_row(self, tx, spec: s.EntitySpec, key: str):
        rows = get_by_pk(tx, spec.table, self._pk_arg(spec, [key]))
        row = rows[0] if rows else None
        return row if (row is not None and row.operation != s.OP_DELETE) else None

    def _current_rows(self, tx, spec: s.EntitySpec, keys: list[str]) -> dict:
        return {s.key_of(spec, r): r for r in get_by_pk(tx, spec.table, self._pk_arg(spec, keys))}

    @staticmethod
    def _same_state(spec: s.EntitySpec, a, b) -> bool:
        if getattr(a, 'operation', None) != getattr(b, 'operation', None):
            return False
        for f in spec.data_fields:
            if getattr(a, f) != getattr(b, f):
                return False
        for f in spec.set_fields:
            if set(getattr(a, f) or []) != set(getattr(b, f) or []):
                return False
        return True

    def _result_change(self, spec, current, resolved):
        if resolved is None:
            if current is not None and current.operation != s.OP_DELETE:
                return dataclasses.replace(current, operation=s.OP_DELETE)
            return None
        if current is not None and self._same_state(spec, current, resolved):
            return None
        return resolved

    def _write_results(self, tx, spec: s.EntitySpec, resolved: dict[str, Any], sequence: int) -> None:
        keys = list(resolved)
        table = spec.table
        per_stmt = max(1, s.MAX_VARS // len(table.row_columns))
        for chunk in s.chunks(keys):
            current = self._current_rows(tx, spec, chunk)
            rows = [r for r in (self._result_change(spec, current.get(k), resolved[k]) for k in chunk)
                    if r is not None]
            for sub in s.chunks(rows, per_stmt):
                params = [v for r in sub for v in table.encode(r, sequence)]
                tx.execute(table.upsert_sql(len(sub)), params)

    def _materialize_many(self, tx, touched, sequence: int) -> None:
        touched = list(touched)
        by_type: dict[str, dict[str, None]] = {}
        for et, key in touched:
            by_type.setdefault(et, {})[key] = None
        for et, keys in by_type.items():
            spec = s.ENTITY_SPECS[et]
            ops = self._enabled_ops_many(tx, et, list(keys))
            self._write_results(tx, spec, {k: resolve(spec, k, ops.get(k, ())) for k in keys}, sequence)
        losers, winners = self._mono_tag_arity(tx, touched)
        fixes: dict[str, dict[str, Any]] = {}
        for et, key in losers:
            fixes.setdefault(et, {})[key] = None
        for (et, key), resolved in winners.items():
            fixes.setdefault(et, {})[key] = resolved
        for et, resolved in fixes.items():
            self._write_results(tx, s.ENTITY_SPECS[et], resolved, sequence)

    def _mono_tag_cells(self, tx, touched) -> dict:
        cells: dict[tuple, set] = {}
        for et, key in touched:
            af = s.TAG_JUNCTIONS.get(et)
            if af is None:
                continue
            pk = dict(zip(s.ENTITY_SPECS[et].pk_fields, s.decode_key(key)))
            cells.setdefault((et, pk[af], pk['property_id']), set()).add(key)
        if not cells:
            return {}
        props = {p.id: p for p in get_entities(tx, s.PROPERTIES, id=list({pid for (_, _, pid) in cells}))}
        out: dict[tuple, set] = {}
        for (et, av, pid), keys in cells.items():
            prop = props.get(pid)
            if prop is None or prop.dtype != s.MONO_TAG_DTYPE:
                continue
            spec = s.ENTITY_SPECS[et]
            rows = get_entities(tx, spec.table, state=0, **{s.TAG_JUNCTIONS[et]: av, 'property_id': pid})
            out[(et, av, pid)] = keys | {s.key_of(spec, r) for r in rows}
        return out

    def _mono_tag_arity(self, tx, touched) -> tuple[set, dict]:
        losers: set = set()
        winners: dict = {}
        for (et, _, _), keys in self._mono_tag_cells(tx, touched).items():
            spec = s.ENTITY_SPECS[et]
            alive = {}
            for key in keys:
                r = resolve(spec, key, self._enabled_ops(tx, et, key))
                if r is not None:
                    alive[key] = r
            if not alive:
                continue
            winner = max(alive, key=lambda k: (alive[k].commit_id, s.decode_key(k)[-1]))
            winners[(et, winner)] = alive[winner]
            losers |= {(et, k) for k in alive if k != winner}
        return losers, winners

    @staticmethod
    def _next_sequence(tx) -> int:
        """Atomically take the next sequence value (DataWriter._exec_get_sequence)."""
        row = tx.execute("UPDATE sequence SET id = id + 1 RETURNING id").fetchone()
        if row is None:
            tx.execute("INSERT INTO sequence (id) VALUES (1)")
            return 1
        return row[0] - 1


# ---------------------------------------------------------------------------
# MediaWriter
# ---------------------------------------------------------------------------

class MediaWriter:
    """Direct writes to media.db (vectors, vector types, maps)."""

    # rows per transaction: keep each write lock short so the backend writer is not starved
    VECTOR_BATCH = 2000

    def __init__(self, write_tx):
        self._write_tx = write_tx

    def upsert_vectors(self, vectors: list[m.Vector]) -> None:
        table = s.VECTORS
        per_stmt = max(1, s.MAX_VARS // len(table.row_columns))
        for batch in s.chunks(list(vectors), self.VECTOR_BATCH):
            with self._write_tx() as tx:
                for sub in s.chunks(batch, per_stmt):
                    tx.execute(table.upsert_sql(len(sub)), [v for r in sub for v in table.encode(r)])

    def delete_vectors(self, type_id: int, sha1s: list[str] | None = None) -> None:
        with self._write_tx() as tx:
            if sha1s is None:
                tx.execute("DELETE FROM vectors WHERE type_id = ?", (type_id,))
            else:
                for chunk in s.chunks(list(sha1s), s.MAX_VARS - 1):
                    tx.execute(f"DELETE FROM vectors WHERE type_id = ? AND {s.where_in('sha1', len(chunk))}",
                               [type_id, *chunk])

    def upsert_vector_type(self, vt: m.VectorType) -> None:
        with self._write_tx() as tx:
            tx.execute(s.VECTOR_TYPES.upsert_sql(1), s.VECTOR_TYPES.encode(vt))

    def delete_vector_type(self, type_id: int) -> None:
        with self._write_tx() as tx:
            tx.execute("DELETE FROM vector_types WHERE id = ?", (type_id,))

    def upsert_map(self, map_: m.Map) -> None:
        with self._write_tx() as tx:
            tx.execute(s.MAPS.upsert_sql(1), s.MAPS.encode(map_))

    def delete_map(self, map_id: int) -> None:
        with self._write_tx() as tx:
            tx.execute("DELETE FROM maps WHERE id = ?", (map_id,))


def read_vector_type(conn, type_id: int) -> m.VectorType | None:
    rows = select_rows(conn, s.VECTOR_TYPES, s.VECTOR_TYPES.model_columns, id=type_id)
    return s.VECTOR_TYPES.decode(rows[0]) if rows else None
