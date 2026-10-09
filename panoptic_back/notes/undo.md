# Undo / Redo — audit of the log-replay system

**Date: 2026-06-10. Verdict: NOT safe yet.** The data-layer replay engine is the right
architecture for non-sequential (per-user) undo, but it has one critical bug, one missing
mechanism (dependency cascade on undo), and the HTTP routes don't implement per-user
semantics at all. 8 of 11 empirical probes failed (probe script reproduced at the bottom).

## How it works today

- Logged (revertable) entities: `properties`, `property_groups`, `tags`,
  `instance_values`, `sha1_values`, `file_values`, `instance_tag_values`,
  `sha1_tag_values`. Each has a `<table>_log` with `PRIMARY KEY (pks…, commit_id)`.
  Structural entities (sources/folders/files/instances) are sequenced-but-not-logged —
  correct per the requirement that only tags / properties / property values are undoable.
  (`property_groups` are also logged — slightly beyond the stated scope, harmless.)
- Every `apply_commit` writes full-state log rows stamped with a fresh `commit_id`
  (`MAX(id)+1` of `commits`). Deletes are soft (row kept with `operation = OP_DELETE`)
  and cascade *at write time* (`_delete_logged` → cascade rows share the same commit).
- Undo = `set_commit_active(commit_id, False)`: flips `commits.active`, then for every
  PK present in that commit's log rows, replays **all** log rows in `commit_id` order,
  skipping disabled commits (`EntitySchema.re_compute` + `merge_logs`), and upserts the
  folded result into the current-state table. Redo = same with `active=True`.
- Replay semantics per table family:
  - `EntitySchema.merge_logs` (props/groups/tags/junctions): needs an active `OP_CREATE`
    to come alive; later `OP_UPDATE` rows overwrite wholesale; `OP_DELETE` kept as tombstone.
  - `PropertyValueSchema.merge_logs` (plain values): last active log row wins.
  - Tag junction rows (`instance_tag_values`/`sha1_tag_values`) are **diffs computed at
    write time** against the then-active tag set (per-tag `OP_CREATE`/`OP_DELETE` rows).

This selective-replay design genuinely supports out-of-order toggling — sequential cases
(`test_data_db.py`) and last-writer-wins value interleavings work. The problems are below.

## BUG 1 (critical): undoing a commit that *created* a row leaves the row alive

`EntitySchema.re_compute` docstring says it: *"PKs whose log produces None (no CREATE ever
seen) are silently skipped."* Skipped means **the stale current-state row is left
untouched** — it is neither deleted nor tombstoned. So undoing the commit that brought a
row into existence is a silent no-op for that row.

Confirmed by probes:

| Scenario | Expected after undo | Actual |
|---|---|---|
| c1 creates property; undo c1 | property gone | property still returned (`operation=1`) |
| c1 creates tag; undo c1 | tag gone | tag still returned |
| c1 sets first value (42) on instance; undo c1 | no value | value 42 still returned |
| c1 assigns tag → junction CREATE row; undo c1 | assignment gone | junction row still active |

This hits **every** logged table and is the root cause of most failures below. It also
means no `sequence` bump happens for these PKs, so delta-sync clients are never told
anything changed (consistent, but consistently wrong).

**Fix:** in `re_compute`, when `merge_logs` yields `None` for a PK that currently has a
row in the main table, upsert a tombstone (`operation = OP_DELETE`, fresh `sequence`)
instead of skipping. Do NOT hard-delete: the tombstone is what delta-sync (`get_since`)
relies on, and the log rows must stay untouched so redo can resurrect the row.

## BUG 2 (critical): no dependency cascade on undo-of-create

Write-time deletes cascade (`_delete_logged` writes cascade rows under the same commit),
but undo of a CREATE is logically also a delete — and nothing cascades:

- A creates tag T (c2). B assigns T to instances (c3). A undoes c2 → even with BUG 1
  fixed, the junction rows from c3 stay active: their PKs are not in c2's log, so
  `re_compute` never visits them. Result: active junction rows pointing to a
  non-existent tag. **Confirmed.**
- Same shape for properties: A creates property P (c1), B writes values (c2), A undoes
  c1 → orphaned `instance_values`/`sha1_values`/`file_values` rows for a dead property.
- Same for a tag used in other tags' `parents` lists (see BUG 5).

**Fix direction:** when toggling commit C, widen the recompute scope beyond C's own log
PKs: also recompute (and referentially filter) dependents —
tags with `list_id` in C's property ids, junction/value rows with `property_id` in C's
property ids, junction rows with `tag_id` in C's tag ids. After replay, any *active*
dependent row whose parent is now dead must be tombstoned in the current table only
(logs untouched). Because logs are untouched, a later **redo** of C re-runs the same
widened recompute and the dependents come back automatically. The cleanup must be
derived (recomputed every toggle), never logged — logging it would corrupt replay.

Cheaper alternative if that's too much: refuse to undo a commit whose created entities
have active references from *other* commits (force the user to undo dependents first or
use explicit delete). Less magic, much simpler to reason about.

## BUG 3: undo/redo routes are global, not per-user

The requirement is per-user undo stacks, but `/undo` picks `max(active commits)` and
`/redo` picks `max(inactive commits)` regardless of who made them, and every route writes
`source='ui'`:

- User A pressing undo reverts user B's latest commit.
- Redo order is wrong even single-user: undo disables ids 9 then 8; redo re-enables
  `max(inactive)=9` first — LIFO violated (last-undone should be redone first).
- There is no "redo stack clearing" — any commit ever undone is redoable forever. In the
  holes-allowed model that's arguably a feature, but combined with diff-base drift
  (EDGE 2 below) it can resurrect surprising state.

**Fix:** put a real user/client id in `Commit.source` (routes currently hardcode `'ui'`);
`/undo` → user's highest *active* commit; `/redo` → user's most recently *deactivated*
commit, which requires recording undo order (e.g. `deactivated_at` timestamp or an
undo-counter column on `commits`) — `min(inactive)` is only correct while undos are
strictly descending.

## BUG 4: full-state UPDATE rows mask earlier edits under non-sequential undo

Log rows store the whole row, not field diffs. So:

- Tag is `(name=cat, color=1)`. A renames → c2 logs `(feline, 1)`. B recolors → c3 logs
  `(feline, 5)` (UI sends full state, so B's row *carries A's name*). A undoes c2 →
  replay folds c1+c3 → still `feline`. **A's undo silently does nothing.** Confirmed.

Same applies to `parents` rewrites, property renames, etc. Plain property values are fine
(last-writer-wins is the natural semantic for a scalar), but multi-field rows lose
per-user undo fidelity. The unused `OP_STAMP_SET` / `OP_STAMP_DIFF` constants in
`data_writer.py` suggest field-diff logging was already anticipated — that is the real
fix. Until then, document that undoing an update only has effect if it is the *latest*
active update of that row.

## BUG 5: deleting a tag leaves children's `parents` dangling

`_cascade_delete_tags` only cascades junction rows. Tags whose `parents` contain the
deleted id keep it (the merge route fixes parents explicitly; plain delete doesn't).
Undo/redo replays that stale state faithfully, so the dangling id survives every replay.
Either cascade a `parents` rewrite at delete time (it then participates in undo
naturally — but see BUG 4 masking), or treat `parents` leniently/filter on read.

## BUG 6 (minor): `/commit/delete` silently drops value deletions

`DeleteRequest.empty_instance_values / empty_image_values / empty_file_values` are
accepted but never processed in `delete_commit_route`. Either implement (write a
null-value / OP_DELETE log row — replay already handles it) or remove the fields.

## Special case: tag merge (`/tags/merge`)

Current flow: one upsert commit (retarget values via full-set writes, fix `parents`,
update main tag) + a **separate** delete commit for the merged-away tags. No shared
`group_id` is passed (the parameter exists end-to-end but is unused, and undo ignores
groups anyway). Consequences:

- One press of undo reverts only the delete half: merged tags come back, but every value
  still points at the main tag — a half-merged state that looks like data loss.
- TOCTOU: the route reads state (`project.get_tags()` etc.), computes the rewrite, then
  writes in separate transactions — a concurrent commit between read and write is folded
  in or lost.

**Recommended fix:** build the merge as a **single `DataCommit`** — it already supports
mixed ops: tag updates (`OP_UPDATE`), tag deletes (`Tag(id, operation=OP_DELETE)`), and
the value rewrites. `apply_commit` applies deletes first (cascading junction `OP_DELETE`
rows for the removed tags under the same commit), then the upsert diffs add the main-tag
rows. One commit ⇒ atomic, and one undo restores the *entire* pre-merge state via normal
replay (verified mentally against the merge_logs rules; needs a test). The route's
read-compute-write should move inside one writer transaction.

If multi-commit operations remain elsewhere, implement group toggling: `set_commit_active`
on every commit sharing a `group_id`, and make `/undo`/`/redo` group-aware.

Merge-specific edge even after the fix: if someone edits a sibling tag's `parents`
*after* the merge, undoing the merge can't restore that tag's old parents (BUG 4 masking).

## Edge cases inherent to the model (document / decide, not bugs per se)

- **EDGE 1 — diff-base drift (junction tables):** junction log rows are diffs against the
  tag set that was active *at write time*. Toggling an older commit changes the base
  under later diffs. Example (confirmed): A sets `{1}` (c2), B sets `{1,2}` (c3 → logs
  only `+2` because 1 was already active). A undoes c2 → desired `{2}`; with BUG 1 fixed
  replay indeed gives `{2}` — but note B *explicitly typed* `{1,2}`, and that intent is
  unrecoverable. Inverse flavour: undo `+a`, then a later commit "clear all tags" logs no
  row for `a` (already gone); redoing the `+a` commit resurrects `a` *after* the clear.
- **EDGE 2 — no-op writes log nothing:** setting a tag set equal to the current one
  writes no junction rows, so that user "confirmation" has no commit to survive an undo
  of the commit that originally added those tags.
- **EDGE 3 — update-after-delete resurrects:** `merge_logs` turns an `OP_UPDATE` arriving
  after a tombstone into a live row (`operation=OP_CREATE`). The live write path behaves
  the same way, so it's at least consistent, but a stale UI editing a deleted tag will
  silently resurrect it.
- **EDGE 4 — `set_commit_active` robustness:** toggling a nonexistent commit raises
  `IndexError` (`COMMITS_SCHEMA.get(...)[0]`); toggling to the same state re-replays
  harmlessly. Worth a guard + 404.
- **EDGE 5 — structural deletes vs logs:** deleting instances/files hard-purges value and
  junction rows *and their logs* (`_delete_instance_values` etc.), so a later undo of an
  unrelated commit can't resurrect values for dead instances. Good — but it also means
  undo history referencing those instances silently shrinks; commits may become empty
  no-ops. Acceptable, just know it.
- **ID allocation is safe:** ids come from `ProjectDB.allocate` (monotonic registry,
  separate db), so undone/deleted ids are never reused — replay identity is stable.

## What is already correct

- Scope: only tags / properties / property values are logged; structural entities are
  excluded from undo (hard-delete + GC). Matches the requirement.
- Sequential undo/redo of updates and deletes (incl. property-delete cascade restore).
- Last-writer-wins interleaving for plain values across users, including redo of an older
  commit not clobbering a newer one (probe passed).
- Write-time delete cascade shares the commit id ⇒ undo of a delete restores the full
  cascaded set atomically.
- Single SQLite writer + `MAX(id)+1` inside the transaction ⇒ commit ids are race-free.

## Priority order

1. BUG 1 — tombstone on `None` merge in `re_compute` (small, mechanical, makes redo/undo
   of creates correct; bump `sequence` so delta-sync sees it).
2. BUG 3 — per-user source on commits + per-user undo/redo selection with recorded undo
   order (this is the actual product requirement).
3. Tag merge as a single commit (removes the worst special case) + group_id toggling as
   the general mechanism for compound operations.
4. BUG 2 — dependency-widened recompute (or the conservative "refuse undo while
   referenced" rule as a stopgap).
5. BUG 5 / BUG 6 / EDGE 4 guards.
6. Decide on BUG 4 (field-diff logs via `OP_STAMP_DIFF`) — biggest design change, needed
   for true per-user fidelity on multi-field rows.

## Repro / probe script

Script saved as `notes/undo_probe.py` (builds a throwaway db per case and exercises
`DataWriter` directly). Run from `panoptic_back/`:
`uv run --no-project --with msgspec,numpy,pydantic,fastapi python notes/undo_probe.py` Results
2026-06-10 on branch `rework-front`: 3/11 pass. Failing: undo-create (property, tag,
value, junction), dangling junction after tag-create undo, rename-undo masked by later
update, `{1}`-undo-after-`{1,2}` keeps `1`. Passing: property-delete-undo restore (tag +
values), redo-older-commit value case.
