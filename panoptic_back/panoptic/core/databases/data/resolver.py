"""resolver.py
~~~~~~~~~~~~~
The versioning core: fold a stream of *enabled* :class:`ChangeOp` partial diffs into the
current, fully-typed row of an entity — or ``None`` when the entity is not alive.

Design (see notes/versioning_architecture.md):

* **State is a pure function of the enabled set**, never of commit order. That is what makes
  undo *non-sequential*: any commit can be toggled at any position, by any user, and the
  result is well-defined. Undo/redo = flip a commit's ``active`` bit and re-resolve the
  entities it touched.
* **Existence is causal.** An entity is alive only after an enabled ``OP_CREATE`` and until a
  later enabled ``OP_DELETE``. A stray ``OP_UPDATE`` on a non-alive entity is ignored — it can
  neither resurrect a deleted row nor materialize one whose creation was undone. This kills the
  historic "stale row" / "resurrection" bugs of the snapshot-fold model.
* **Granularity is the cell.** Scalars fold as last-writer-wins registers; set fields
  (``tag.parents``) fold as OR-Sets of per-element add/remove. Two users editing different
  cells never collide, so an undo reverts only the cells its commit actually owned.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable, Optional

import msgspec

from panoptic.core.databases.entity_schema import (
    EntitySchema, OP_CREATE, OP_UPDATE, OP_DELETE,
)
from panoptic.core.databases.data.create import LOGGED_ENTITY_META
from panoptic.core.databases.data.models import ChangeOp


# ---------------------------------------------------------------------------
# Entity specs — one per logged entity kind, derived from create.LOGGED_ENTITY_META
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EntitySpec:
    entity_type:   str
    struct:        type
    schema:        EntitySchema        # result (current-state) table
    pk_fields:     tuple               # primary-key field names, in struct order
    data_fields:   tuple = ()          # scalar fields folded as LWW registers
    set_fields:    tuple = ()          # fields folded as OR-Sets (stored as JSON lists)
    presence_only: bool  = False       # junction rows: existence only, no payload


ENTITY_SPECS: dict[str, EntitySpec] = {
    entity_type: EntitySpec(
        entity_type, schema.struct_cls, schema, tuple(pk_fields),
        data_fields=tuple(data_fields), set_fields=tuple(set_fields),
        presence_only=presence_only,
    )
    for (entity_type, schema, pk_fields, data_fields, set_fields, presence_only)
    in LOGGED_ENTITY_META
}


# ---------------------------------------------------------------------------
# Key encoding — a JSON pk tuple lets one log table hold every entity kind
# ---------------------------------------------------------------------------

def encode_key(pk: tuple | list) -> str:
    return json.dumps(list(pk), separators=(',', ':'))


def decode_key(key: str) -> list:
    return json.loads(key)


def key_of(spec: EntitySpec, obj: msgspec.Struct) -> str:
    return encode_key(tuple(getattr(obj, f) for f in spec.pk_fields))


# ---------------------------------------------------------------------------
# Diff (write path): current typed row + incoming typed row -> ChangeOp.changes
# ---------------------------------------------------------------------------

def diff_changes(spec: EntitySpec, current: Optional[msgspec.Struct],
                 incoming: msgspec.Struct) -> dict:
    """Return the minimal ``changes`` dict taking ``current`` to ``incoming``.

    On create (``current is None``) every non-None field is emitted (the base image);
    set fields are emitted as an all-``add`` delta. On update only differing fields are
    emitted; set fields as an add/remove delta.
    """
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


# ---------------------------------------------------------------------------
# Resolve (read/undo path): enabled ops -> typed row or None
# ---------------------------------------------------------------------------

def resolve(spec: EntitySpec, key: str, ops: Iterable[ChangeOp]) -> Optional[msgspec.Struct]:
    """Fold enabled ops (ascending commit order) into a typed result row, or None if dead.

    ``ops`` MUST already be filtered to enabled commits and sorted by commit id.
    """
    alive = False
    last_commit = None
    scalars: dict[str, Any] = {}
    sets: dict[str, dict[Any, bool]] = {f: {} for f in spec.set_fields}

    for op in ops:
        last_commit = op.commit
        if op.op == OP_DELETE:
            alive = False
            continue
        if op.op == OP_CREATE:
            alive = True
        elif not alive:
            # OP_UPDATE on a non-alive entity: cannot update what does not exist. Ignore —
            # this is the causal rule that prevents resurrection / undone-creation ghosts.
            continue
        for k, v in (op.changes or {}).items():
            if k in sets:
                m = sets[k]
                for x in v.get('remove', ()):
                    m[x] = False
                for x in v.get('add', ()):
                    m[x] = True
            else:
                scalars[k] = v

    if not alive:
        return None

    fields: dict[str, Any] = dict(zip(spec.pk_fields, decode_key(key)))
    for f in spec.data_fields:
        if f in scalars:
            fields[f] = scalars[f]
    for f in spec.set_fields:
        fields[f] = sorted(k for k, present in sets[f].items() if present)
    fields['commit_id'] = last_commit
    fields['operation'] = OP_CREATE
    return spec.struct(**fields)
