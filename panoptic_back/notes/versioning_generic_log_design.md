# Typed Result Tables + Generic Partial-Diff Log — Design

Builds on `versioning_replay_analysis.md`, `versioning_revert_complexity.md`,
`versioning_multiuser_undo.md`.

Idea: keep the **materialized (result) tables strongly typed** — a full `Property`, full
`Tag`, full `PropertyGroup` row, read directly with no reconstruction — but replace the
per-entity full-snapshot `_log` tables with **one generic log** whose rows carry only the
**changed fields as a dict**. Field-level diffs give field-level undo granularity (minimal
multi-user collateral) and a much smaller, uniform log.

---

## 1. Shape

```
                    write path                         read path
  UI action ──▶ diff vs current ──▶ ChangeOp{changes:dict}  ──▶  entity_log (generic)
                     │
                     └──▶ apply changes ─────────────▶ properties / tags / groups (TYPED, full rows)
                                                              ▲
  undo(commit) ─▶ disable ─▶ re-resolve touched entities ────┘   (fold enabled ChangeOps)
```

- **Result tables**: unchanged typed structs (`Property`, `Tag`, `PropertyGroup`) holding the
  *current resolved state*. Reads hit these directly — no folding at read time. They keep a
  `sequence` column for delta-sync. They no longer need `commit_id`/`operation` (existence is
  driven by the log) — though keeping `operation` as a soft-delete/tombstone marker for
  delta-sync is convenient (see §6).
- **Log**: a single generic `entity_log` table of partial diffs, one row per (entity, commit).

This applies to the **single-PK logged entities** (`property`, `tag`, `property_group`). The
already-fine-grained per-element tables (`instance_tag_values`, `sha1_tag_values`, the value
tables) stay as they are — they're already "one cell per row".

---

## 2. The generic log object

```python
# models.py
class ChangeOp(msgspec.Struct, array_like=True):
    entity_type: Annotated[str, PrimaryKey]   # 'property' | 'tag' | 'group'
    entity_id:   Annotated[int, PrimaryKey]
    commit_id:   Annotated[int, PrimaryKey]
    op:          int                          # OP_CREATE | OP_UPDATE | OP_DELETE
    changes:     Optional[dict] = None        # {field: value}; for sets: {field: {'add':[...], 'remove':[...]}}
    sequence:    Optional[int] = None
```

Table (composite PK, two indexes):

```sql
CREATE TABLE entity_log (
    entity_type TEXT, entity_id INTEGER, commit_id INTEGER,
    op INTEGER NOT NULL, changes JSON, sequence INTEGER,
    PRIMARY KEY (entity_type, entity_id, commit_id)
);
CREATE INDEX idx_entity_log_commit ON entity_log (commit_id);              -- fetch a commit's ops (undo)
CREATE INDEX idx_entity_log_entity ON entity_log (entity_type, entity_id, commit_id);  -- fold one entity
```

`changes` semantics by op:
- `OP_CREATE`: the full initial field set (base image).
- `OP_UPDATE`: **only the fields that changed**, `{field: new_value}`. Scalars carry the new
  value; set-typed fields (e.g. `tag.parents`) carry `{'add': [...], 'remove': [...]}`.
- `OP_DELETE`: `changes = None`.

`commits(id, author, timestamp, enabled, group_id)` — `enabled` replaces `active`; `author`
enables per-user undo.

---

## 3. Per-entity field spec

One small registry drives generic diffing and resolution:

```python
FIELD_SPEC = {
    'property': dict(struct=Property,      set_fields=frozenset()),
    'tag':      dict(struct=Tag,           set_fields=frozenset({'parents'})),
    'group':    dict(struct=PropertyGroup, set_fields=frozenset()),
}
```

`set_fields` are resolved as OR-Sets (add/remove per element, add-wins or timestamp-wins);
everything else is a scalar LWW register.

---

## 4. Write path — diff to changed fields only

```python
def apply_entity_change(tx, entity_type, new: msgspec.Struct, commit_id, seq):
    spec   = FIELD_SPEC[entity_type]
    eid    = new.id
    cur    = get_materialized(tx, entity_type, eid)          # typed row or None

    if cur is None:
        changes = _nonnull_fields(new)                        # full base image
        op = OP_CREATE
    else:
        changes = {}
        for f in _data_fields(spec['struct']):
            nv, ov = getattr(new, f), getattr(cur, f)
            if f in spec['set_fields']:
                add, rem = set(nv or []) - set(ov or []), set(ov or []) - set(nv or [])
                if add or rem:
                    changes[f] = {'add': sorted(add), 'remove': sorted(rem)}
            elif nv != ov:
                changes[f] = nv
        if not changes:
            return                                            # no-op, nothing logged
        op = OP_UPDATE

    ENTITY_LOG.append(tx, ChangeOp(entity_type, eid, commit_id, op, changes), sequence=seq)
    # apply to the typed result table (merge changes into cur / insert new), stamp sequence
    _apply_changes_to_materialized(tx, entity_type, eid, cur, changes, op, seq)
```

Deletes append `ChangeOp(..., op=OP_DELETE, changes=None)` and tombstone the result row.

Key property: **the log records the minimum** — only what this commit actually altered. Two
users editing different fields of the same entity produce **disjoint** `changes` dicts.

---

## 5. Resolution — fold partial diffs into a full typed row

```python
def resolve(entity_type, eid, ops):        # ops = enabled ChangeOps, ascending commit_id
    spec  = FIELD_SPEC[entity_type]
    alive = False
    vals: dict = {}
    sets: dict[str, dict[int, bool]] = {f: {} for f in spec['set_fields']}

    for o in ops:
        if o.op == OP_CREATE:
            alive = True
            for k, v in (o.changes or {}).items():
                _put(k, v, vals, sets, spec)
        elif o.op == OP_DELETE:
            alive = False                    # existence LWW; fields kept dormant
        else:  # UPDATE
            for k, v in (o.changes or {}).items():
                _put(k, v, vals, sets, spec)

    if not alive:
        return None                          # → caller writes a tombstone

    for f, members in sets.items():
        vals[f] = sorted(k for k, present in members.items() if present)
    return spec['struct'](id=eid, **vals)    # FULL typed row

def _put(field, v, vals, sets, spec):
    if field in spec['set_fields']:
        m = sets[field]
        for x in v.get('remove', ()): m[x] = False
        for x in v.get('add', ()):    m[x] = True   # add-wins within a commit
    else:
        vals[field] = v                             # scalar LWW: later enabled op wins
```

Because each `UPDATE` only carries the fields it changed, the final value of a field is the
**last enabled op that wrote that field** — i.e. per-field LWW, for free. `parents` is a real
OR-Set, so concurrent `add P1` / `add P2` both survive.

---

## 6. Undo / redo

```python
def set_commit_enabled(commit_id, enabled):
    seq = next_sequence()
    set commits.enabled = enabled
    touched = ENTITY_LOG.get(commit_id=commit_id)          # O(rows in this commit) — one index probe
    by_entity = group touched by (entity_type, entity_id)
    for (etype, eid) in by_entity:
        ops = enabled_ops_for(etype, eid)                  # fold this entity's enabled history
        row = resolve(etype, eid, ops)
        if row is None:
            tombstone_materialized(etype, eid, seq)        # visible deletion for delta-sync
        else:
            upsert_materialized(row, seq) if changed       # only stamp seq if value actually changed
```

- **Non-sequential / any position / any user:** state = fold over the *enabled* set, so it's
  order-independent. Undoing user A's commit re-resolves only the entities A touched; other
  entities are never read or written.
- **Cost:** `O(entities touched × that entity's enabled-history length)`. History per entity
  is normally short. To make it strictly `O(changed fields)` add **field provenance** (§7).
- **Per-user undo:** pick `max enabled commit_id where author = me`, disable it. Redo is the
  inverse.

### Field-provenance optimization (optional, → O(changed fields))
Store on the result table, per scalar field, the `commit_id` that currently owns it
(a small `provenance JSON` column, or a side table). On undo of X, a field only needs
recomputation if its provenance == X; then fetch that field's previous enabled writer
(`MAX(commit_id) < X` among enabled ops whose `changes` contain the field). This skips
entities/fields X didn't actually win, turning undo into `O(fields X currently owns)`.

---

## 7. Delta-since-sequence

Unchanged and still `O(delta)`:
- Only the **result tables** carry `sequence`; `get_since(S)` = `WHERE sequence > S`.
- An edit or an undo re-stamps a result row **only if its resolved value changed** → the
  reported delta is exactly the entities whose visible state changed, from edits *or* undos.
- Deletions are tombstones (result row flagged deleted + new sequence), so removals are
  visible to clients; never hard-delete on undo.
- The generic `entity_log` doesn't need `sequence` for clients (they sync the typed result),
  but keeping one lets a client rebuild its own undo stack by `author`.

---

## 8. Why this shape

| Concern | Outcome |
|---|---|
| Read performance | Reads hit typed result tables directly — **no fold at read time**. |
| Log size | One uniform table; rows store **only changed fields**, not full snapshots. |
| Multi-user collateral | Field-level diffs ⇒ disjoint edits never collide; undo reverts only the fields a commit owns. |
| Non-sequential undo | State = fold over the enabled set ⇒ order-independent, any position, any user. |
| Adding a field/entity | Result struct + one `FIELD_SPEC` line; the generic log/resolver are untouched. |
| Partial updates (note P3) | First-class: partial `changes` is the native unit; no more "must send full snapshot". |

### Trade-offs / watch-outs
- **Diffing needs the current row** on write (already fetched today) — cheap.
- **Set fields** (`parents`) must go through the add/remove path, not whole-list replace, or
  concurrent parent edits will still collide. Enforce in `apply_entity_change`.
- **Referential integrity** across entities (a `parents` element referencing an undone tag)
  is still resolved at **read time** (filter non-alive refs), exactly as in the multi-user
  note §8 — this design doesn't change that.
- **`changes` typing:** it's a generic `dict`, so the log loses per-field static typing;
  validate against the target struct's fields on write (reject unknown keys) to keep it honest.

---

## 9. Migration from current schema

1. Add `entity_log` + `commits.author` + `commits.enabled` (rename from `active`).
2. Backfill: for each existing `<t>_log` snapshot chain, emit `ChangeOp`s by diffing
   consecutive snapshots (first = CREATE with full fields, deletes → OP_DELETE). One-time.
3. Drop `properties_log` / `tags_log` / `property_groups_log`; drop `commit_id`/`operation`
   from the result tables (keep an `operation`/`deleted` tombstone marker if simpler for
   delta-sync).
4. Leave junction + value tables as-is (already cell-grained); optionally fold them into the
   same generic mechanism later.

---

## 10. Bounding resolution cost — log compaction (no snapshot subsystem)

Reads are already O(1) (typed result tables). The only cost to bound is **resolve**, run at
toggle time for the entities a toggled commit touched: `O(h_E)` = length of E's enabled
history. We bound it **not** with a snapshot table but by **compacting the settled prefix of
the log into a frozen genesis commit** and removing the ability to undo behind it.

### Where the start state lives
As **ordinary log rows**, not a side table. Compaction rewrites all commits `≤ H` into a
single frozen genesis commit `H0` whose rows are full-field `CREATE` `ChangeOp`s — one per
surviving entity:

```
log after compaction at horizon H:
  genesis H0 (frozen):  ChangeOp('property', P, H0, CREATE, {all fields})   ← folded start state
                        ChangeOp('tag',      T, H0, CREATE, {all fields})
                        …one per surviving entity…
  tail (H, now]:        normal partial-diff ChangeOps, fully toggleable
```

The resolver is unchanged — it always folds from genesis forward. Per-entity resolve becomes
`O(1 genesis + that entity's tail ops)` ≤ **`O(W)`**, where `W` = retained commit window.

### Compaction procedure
1. Choose `H` (see watermark rule below).
2. For each entity touched `≤ H`: fold its **enabled** ops `≤ H` → emit one frozen `CREATE`
   with the full folded fields. An entity that folds to *dead* (created and deleted `≤ H`)
   gets **no** genesis row and is hard-deleted.
3. Delete all log rows and `commits` rows with `commit_id ≤ H` (or collapse into `H0`).
4. Same fold for the value/junction tables' prefixes.
5. **GC point:** dormant/orphaned dependent rows whose owning entity died `≤ H` are physically
   removed here — now safe, because their commit is no longer undoable.

### Why middle-removal can't corrupt a genesis
Toggling is allowed only for commits `> H`. The genesis contains **no toggleable commit**, so
no later undo can invalidate it. A toggle inside the tail is just a tail refold (`≤ W`); a
commit behind `H` is permanently baked in (if enabled at compaction) or permanently dropped
(if disabled at compaction). Compaction is **irreversible** — the accepted price for the bound.

### Multi-user watermark rule
`H` must trail behind **every** user's oldest still-undoable commit:
```
H = min over active users of (oldest reachable undo commit) − margin
```
Compact lazily in the background up to this "settled" watermark so `W` stays small without
ever amputating a live undo.
