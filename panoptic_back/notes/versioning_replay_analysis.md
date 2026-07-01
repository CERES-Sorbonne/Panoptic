# Versioning / Replay Logic — In-Depth Analysis & Proposal

Scope: `panoptic/core/databases/data/` (`data_writer.py`, `entity_schema.py`,
`data_reader.py`, `create.py`, `models.py`) plus the callers in
`routes/project_routes.py` (undo/redo, tag merge).

---

## 1. How the model works today

### Two classes of entity
- **Structural** (`file_sources`, `folders`, `files`, `instances`): *sequenced but
  not logged*. Delta-synced via a monotonic `sequence` column, hard-deleted, **never
  undone**. No `commit_id`/`operation` columns, no `_log` table.
- **Logged / trackable** (`properties`, `property_groups`, `tags`, `instance_values`,
  `sha1_values`, `file_values`, `instance_tag_values`, `sha1_tag_values`): every write
  is appended to a `<table>_log` table and participates in undo/redo.

A struct is "trackable" iff it declares both `commit_id` and `operation`
(`entity_schema.py:103`, `:179`).

### Tables per logged entity
- **Main table** = *current computed state*. One row per PK. Carries `operation`
  (`CREATE=1`, `UPDATE=0`, `DELETE=-1`) + `sequence`. Reads filter soft-deletes:
  `get(state=1)` → `operation IN (CREATE, UPDATE)` (`entity_schema.py:583`).
- **Log table** = append-only journal. PK is `(<entity pks…>, commit_id)`. Each row is
  a **full snapshot** of the entity at that commit, tagged with its `operation`.

### Writing a commit — `apply_commit` (`data_writer.py:35`)
1. Allocate `commit_id = max(id)+1`, `sequence = _exec_get_sequence`.
2. Partition the `DataCommit` into upserts vs. deletes.
3. Cascade + soft-delete the deletes (`_delete_logged`).
4. For each upsert (`_upsert_commit_*`): decide `operation = CREATE if id not in main
   else UPDATE`, write merged state to the main table, and `append_log` the raw object.
5. Insert the `Commit` row with `active=True`.

### Undo/redo — `set_commit_active` (`data_writer.py:275`)
1. Flip `commit.active`.
2. `disabled = {c.id for c in commits if not c.active}`.
3. For every logged schema: take the PKs touched by *this* commit's log, then
   `re_compute` them.

### The replay core — `re_compute` (`entity_schema.py:903`)
For each affected PK: fetch **all** its log rows across **all** commits in `commit_id`
order, drop rows whose commit is in `disabled`, fold the survivors with `merge_logs`,
and **upsert** the result into the main table.

### The fold — `merge_logs`
- `EntitySchema.merge_logs` (`entity_schema.py:885`): walks entries in order.
  `current` stays `None` until the **first `CREATE`**. After that, a `DELETE` sets
  `current` to a delete-tombstone; **any non-delete (incl. `UPDATE`) sets `current` to
  that whole object as a live `CREATE`.** It is *last-writer-wins on the full snapshot*,
  not a field-level merge.
- `PropertyValueSchema.merge_logs` (`entity_schema.py:966`): even simpler — return the
  **last non-None** entry verbatim (no CREATE bootstrap, no delete logic).

The single invariant the whole scheme rests on:

> **every log row is a complete snapshot, and the active set of commits for any entity
> forms a valid causal chain that begins with a CREATE.**

Both halves of that invariant are violated in practice. That is the root of the bugs.

---

## 2. Problems

### P1 — `re_compute` never deletes; folding to `None` leaves a stale row  ⭐ root cause
`re_compute` only **upserts** merged results (`entity_schema.py:951`). Its own docstring
admits it: *"PKs whose log produces `None` … are silently skipped."* When the fold
returns `None`, the previously-computed main-table row is **left untouched** — it does
not disappear, and its `sequence` is not bumped, so **delta-sync never tells the client
it's gone either**.

`merge_logs` returns `None` whenever the surviving (enabled) entries contain **no
CREATE** — e.g. the CREATE commit is disabled but a later UPDATE is still enabled.

**Concrete trace — "create, modify, then reset creation":**
```
C1: CREATE property P (name="foo")
C2: UPDATE property P (name="bar")
undo until C1 disabled, C2 still enabled   →  disabled={1}
re_compute(P): enabled log = [C2:UPDATE]   →  merge_logs → None  (no CREATE)
```
P remains in the main table with C2's state. Its creation was undone, yet it is still
visible and still syncs as present. **Integrity broken.**

This is the same failure behind the reported "reversing tag merges" and "changing
parents then undoing the create" cases — they all bottom out in *fold → None → stale
row not removed*.

### P2 — `merge_logs` resurrects deleted entities via a later UPDATE
In the fold, after a `DELETE`, the next `UPDATE` hits the `else` branch and revives the
entity as a live `CREATE` (`entity_schema.py:899`).

```
C1: CREATE P   C2: DELETE P   C3: CREATE P (re-create)   C4: UPDATE P
disable C3 only  →  enabled = [C1:CREATE, C2:DELETE, C4:UPDATE]
fold: CREATE → live; DELETE → dead; UPDATE → LIVE again   →  P resurrected
```
An `UPDATE` should never resurrect a deleted entity — "update" presupposes existence.
The fold conflates "latest snapshot" with "is-alive", so disabling a re-CREATE silently
brings the row back through an unrelated later edit.

### P3 — Full-snapshot assumption vs. partial writes
`merge_logs` never merges fields; it replaces `current` wholesale. Both the forward path
(`_upsert_commit_properties` does `merge_logs([existing, p])`, `data_writer.py:371`) and
replay therefore assume **every** logged write carries **every** field. Any caller that
sends a partial update (e.g. a `Tag` with only `parents` set, other fields `None`) will
have those fields silently nulled on the *next* replay — even though the forward write
looked fine at the time. This is a latent corruption that only surfaces on undo/redo.

### P4 — Multi-commit operations are not atomic and not grouped
Tag merge (`project_routes.py:1464`) performs **two independent commits**:
```python
project.apply_upsert_commit('ui', upsert)          # rewrites tags + values
project.apply_delete_commit('ui', DeleteCommit(tags=removed_ids))   # deletes tags
```
Each gets its own `group_id` (defaults to its own `commit_id`, `data_writer.py:43`).
`undo` toggles a **single** max-id commit (`project_routes.py:1121`). So undoing a merge
reverts only the tag-deletion half, leaving instance/sha1 values pointing at the merged
target while the removed tag entity reappears — an inconsistent intermediate state. A
second undo is required, and nothing guarantees the two stay together.

### P5 — Undo/redo is positional (max id), not a causal stack
`undo` = disable `max(active id)`; `redo` = enable `max(inactive id)`
(`project_routes.py:1114-1134`). There is no HEAD pointer and no contiguity check, so the
**active set can become non-contiguous**, which directly manufactures the P1/P2
preconditions:
```
C9:  CREATE tag T
C10: UPDATE tag T (rename)
undo → disable C10 ; undo → disable C9
redo → enables max inactive = C10   (C9 still disabled!)
re_compute(T): enabled = [C10:UPDATE] → None → stale row (P1)
```
Redo re-enabled the rename without re-enabling the creation. A positional scheme cannot
express "these commits depend on each other."

### P6 — Replay has no cross-entity referential integrity
Every schema is replayed independently over its own PKs. But logged entities reference
each other: `Tag.parents → tag ids`, `Property.tag_list_id`, `Property.property_group_id`,
`instance_tag_values.tag_id → tag`. Disabling the commit that created tag A does **not**
reconcile:
- child tags whose `parents` list still contains A (dangling parent), or
- `instance_tag_values` rows whose `tag_id = A` (value referencing a non-existent tag).

`re_compute` is called per-schema on PKs touched by *the toggled commit only*
(`data_writer.py:297-304`), so entities that merely *reference* the toggled ones are
never revisited. Result: dangling parents and orphan tag assignments after partial undo —
the "changing parents" corruption.

### P7 — `set_commit_active` recomputes the global `disabled` set but only re-plays one commit's PKs
Toggling commit X recomputes only entities X touched. If a *different* commit Y is
already disabled and shares no PKs with X, that's fine — but any entity whose correct
state depends on the interaction of X and Y is only fixed if X happened to touch it.
This is the mechanism that lets non-contiguous disables (P5) leave the DB in a state that
is not equal to "replay everything with `disabled` applied." **The main table can diverge
from a clean full replay.** (Good invariant to test: after any toggle, the main table must
equal a from-scratch replay of all enabled commits.)

---

## 3. Proposed solution

Two independent axes: (A) make the **fold + replay** correct and total; (B) make
**undo/redo** a coherent, grouped, causal operation. Do A first — it fixes the data
corruption; B removes the ways users reach the corrupt states.

### A1. Make `re_compute` total — tombstone instead of skip
Compute a target state for **every** PK in `pk_list`, not just those that fold to a live
object. For each PK:
- fold → live object (`op ∈ {CREATE, UPDATE}`): upsert as today;
- fold → `None` **or** a delete: **upsert a DELETE tombstone** for that PK (we already
  have the PK), with the new `sequence`.

Tombstone (not hard delete) so that `get(state=1)` hides it *and* `get_since` reports the
change to clients. This single change eliminates every "stale row" symptom (P1, tag-merge
reversal leaving the target tag, undo-of-create). For `PropertyValueSchema`, same rule:
all-disabled / empty → tombstone the PK.

### A2. Fix `merge_logs` causal semantics (kill resurrection)
Replay must model *aliveness*, not just "latest snapshot":
```
current, alive = None, False
for obj in entries:            # enabled, commit order
    if obj.operation == CREATE:            current, alive = obj, True
    elif obj.operation == DELETE:          current, alive = tombstone(obj), False
    elif obj.operation == UPDATE:
        if alive:                          current = as_live(obj)
        # else: ignore — cannot update a non-existent entity
return current if alive else tombstone-or-None
```
This makes P2 impossible and makes "disable the CREATE" deterministically yield a dead
entity regardless of later UPDATEs.

### A3. Enforce full snapshots (or make merge field-level)
Pick one and enforce it:
- **Cheap:** assert at `append_log` that no non-key field is `None` unless intentionally
  nullable, and audit callers to always send complete objects. Document the invariant.
- **Robust:** change `merge_logs` to fold field-by-field (carry prior field when the new
  snapshot's field is a sentinel/`UNSET`). Requires distinguishing "unset" from "set to
  null" — msgspec `UNSET` supports this. This removes the P3 latent-corruption class
  entirely and enables true partial updates.

### B1. One operation = one commit (atomicity)
`apply_commit` already accepts a unified `DataCommit` that can create, update **and**
delete in a single commit (`data_writer.py:35`). Rewrite `merge_tags_route` to emit a
**single** `DataCommit` containing the tag/value upserts *and* the `Tag(operation=DELETE)`
rows, instead of `apply_upsert_commit` + `apply_delete_commit`. Do the same for any other
multi-step mutation. Atomic undo falls out for free.

### B2. Undo/redo by group, as a real stack
- Give every logical operation a shared `group_id` (already threadable through
  `apply_commit(..., group_id=...)`).
- Undo/redo toggle **all commits in a group** together, and move a single **HEAD pointer**
  over groups in `commit_id` order rather than picking `max(id)` positionally.

### B3. Enforce linear (contiguous) history — recommended default
Constrain the active set to a prefix of history: you may only disable the current HEAD
group, and only re-enable the group immediately after HEAD. This structurally guarantees a
CREATE is never disabled while a dependent later edit stays enabled, which kills P5/P6/P7
at the source. Selective (non-linear) commit toggling is a much harder feature (needs a
real dependency graph); don't support it unless there's a product requirement.

If non-linear toggling is truly required later, add **A4**: after any toggle, run a
referential-integrity reconciliation pass (prune dangling `parents`, tombstone
`instance_tag_values`/`sha1_tag_values` whose `tag_id` is no longer live, etc.) and/or
expand the re_compute PK set to the transitive closure of referencing entities.

### Correctness harness (add regardless)
Add a property-based test asserting the core invariant after every toggle:

> `main table state  ==  full from-scratch replay of all enabled commits`

Drive it with randomized sequences of the exact edge cases: create→update→disable-create;
delete→recreate→disable-recreate; tag merge→undo; set-parents→undo-create-of-parent;
non-contiguous disable/enable. Every problem above shows up as a divergence.

---

## 4. Priority

| Fix | Removes | Effort |
|-----|---------|--------|
| A1 tombstone in `re_compute` | P1 + all "stale row" symptoms | low |
| A2 causal `merge_logs` | P2 resurrection | low |
| B1 single-commit operations | P4 atomicity | low (rewrite merge route) |
| B3 linear grouped undo/redo | P5, P6, P7 | medium |
| A3 snapshot enforcement | P3 latent corruption | low (assert) / medium (UNSET merge) |
| A4 referential reconcile | P6 under non-linear undo | high — only if needed |

A1 + A2 are the highest-leverage: a few lines each, and together they restore the
"replay == current state" invariant for the linear case. B1 + B3 then prevent users from
constructing the pathological histories in the first place.
