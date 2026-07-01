# Versioning Architecture — Goal, Rationale, Benefits & Limitations

**Status:** implemented in `panoptic/core/databases/data/` (see §7 below). This is the
entry-point note; the mechanics live in the companions:
- `versioning_replay_analysis.md` — what's wrong with the current model.
- `versioning_generic_log_design.md` — the concrete schema (typed tables + generic log) and
  log compaction.
- `versioning_multiuser_undo.md` — per-cell resolution & multi-user semantics.
- `versioning_revert_complexity.md` — cost analysis.

---

## 1. Why we are changing this

The current model stores, per logged entity, a `_log` table of **full-row snapshots** and
recomputes state by folding a PK's entire history against a global `disabled` set
(`re_compute` in `entity_schema.py`). It has four structural problems:

1. **Correctness under partial undo.** Folding requires an enabling `CREATE`; disabling a
   creation while a later update stays enabled yields either a stale row that never
   disappears or a resurrected entity. (Analysis note P1/P2.)
2. **Cost.** One revert is `O(number of commits + Σ full history depth of every entity the
   commit touched)` — it grows with project age and with how heavily-edited the touched
   entities are, not with the size of the action. (Complexity note.)
3. **Granularity.** The unit of change is a whole row, so two users editing *different
   fields* of the same property collide, and undoing one reverts the other.
4. **Single-user, linear only.** Undo/redo is a positional `max(id)` toggle; it cannot
   express "undo *my* change in the middle of a shared history without touching yours."

The product goal is the opposite of all four: **multiple users editing one project, each able
to undo their own work at any position in the log, with the smallest possible collateral on
everyone else, at a bounded cost, and with cheap incremental sync.**

---

## 2. The goal architecture

Seven pieces. Each exists to satisfy a specific requirement.

### 2.1 Typed result tables (the read cache)
`properties`, `tags`, `property_groups`, value/junction tables hold the **current resolved
state** as fully-typed rows. Reads hit them directly — **no folding at read time**. They
carry a `sequence` column for delta-sync. *Why:* reads must stay O(1) and strongly typed.

### 2.2 Generic partial-diff log (the source of truth)
One uniform `entity_log` of `ChangeOp{entity_type, entity_id, commit_id, op, changes:dict}`,
where `changes` holds **only the fields a commit altered** (scalars = new value; sets =
`{add,remove}`; delete = none). *Why:* a compact, uniform journal, and — crucially — the diff
*is* the unit of undo, giving field-level granularity for free.

### 2.3 Enabled-set model (order independence)
Each commit has an `enabled` bit and an `author`. **Materialized state is a pure function of
the set of enabled commits — never of their order.** Undo/redo = flip a bit and re-resolve
the affected entities. *Why:* this is what makes undo *non-sequential* — you can toggle a
commit in the middle of history, by any user, and the result is well-defined.

### 2.4 Per-field / per-cell resolution (minimal collateral)
Resolution folds a cell's enabled ops: **scalars as last-writer-wins registers, sets
(`parents`, tag membership) as OR-Sets.** Existence is a boolean LWW cell (`CREATE`/`DELETE`).
*Why:* the conflict unit shrinks from a row to a cell, so disjoint edits never interfere and
an undo only reverts the exact fields its commit owned.

### 2.5 Read-time referential filtering (safe cross-entity undo)
Cross-entity references (`tag.parents → tag`, `property.tag_list_id`, an assignment's
`property_id`/`tag_id`) are **not reconciled by editing on undo** — that would revert other
users' work. Instead references to non-alive entities are **filtered at read/delta/aggregate
time**; the referencing op is left intact and reappears automatically on redo. *Why:* keeps
undo O(local) and non-destructive; dependent data goes dormant, never lost.

### 2.6 Log compaction with an undo horizon (bounded cost — no snapshots)
We do **not** build a snapshot subsystem. To bound resolution cost we **fold the settled
prefix of the log into a single frozen genesis commit** (full-field `CREATE` ops, stored as
ordinary log rows) and drop the commits behind it. Undo cannot reach behind the horizon `H`.
*Why:* per-entity resolve becomes `O(genesis + tail)` ≤ `O(W)` where `W` = retained commit
window, with no separate snapshot table and no change to the resolver. Compaction is also the
**GC point** where dormant/orphaned dependent rows are physically removed. `H` must trail
behind every user's oldest still-undoable commit.

### 2.7 Delta-since-sequence (cheap sync)
Only result tables carry the monotonic `sequence`; `get_since(S)` = `WHERE sequence > S`. An
edit or an undo re-stamps a row **only if its resolved value actually changed**, so the
reported delta is exactly the cells that changed — from anyone's edit *or* undo. Deletions are
tombstones (never hard-delete on undo) so removals stay visible.

---

## 3. How it holds together (one line each)

- Write → diff to `changes` → append `ChangeOp`, patch typed row, bump `sequence`.
- Read → typed table directly, filtering non-alive references.
- Undo/redo → flip `enabled`, re-resolve only touched entities' affected cells, re-stamp
  changed rows.
- Sync → `get_since(sequence)` returns the changed rows.
- Compaction → fold settled prefix into frozen genesis, GC the dead, advance `H`.

---

## 4. Benefits

- **True multi-user concurrent undo.** Any user undoes their own commit at any position;
  others' disjoint work is untouched.
- **Minimal collateral — the physical floor.** Users interfere only when they write the
  *same cell*. Different columns / different tags / different instances never conflict.
- **Non-destructive & self-healing.** Undo hides, never deletes; redo restores concurrent
  work intact (verified against the "revert a property creation while another user populated
  it" scenario — see design note).
- **Bounded revert cost.** `O(W)` per touched entity (O(changed fields) with provenance),
  independent of total history and project age.
- **O(1), strongly-typed reads.** No fold on the read path.
- **Cheap, exact delta-sync.** Clients receive precisely the cells that changed.
- **Correct by construction.** Existence-as-LWW kills the stale-row / resurrection bugs of
  the current model.
- **Compact, uniform log** and **first-class partial updates** (no "must send a full
  snapshot" trap).
- **Small blast radius to extend.** New field/entity = a struct field + one `FIELD_SPEC`
  line; the generic log and resolver are untouched.

---

## 5. Limitations & tradeoffs (accepted)

- **Undo is bounded by the horizon.** Once the prefix is compacted, commits behind `H` are
  permanently non-undoable. This is the deliberate price of a bounded cost — there is **no
  unlimited selective undo of any commit ever**.
- **Compaction is irreversible** and must trail every user's undo window (`H = min undo
  pointer − margin`); mis-setting it can amputate a live undo, so the watermark logic must be
  conservative.
- **Same-cell concurrent writes still race.** Resolved by LWW (timestamp/commit order);
  inherent to concurrent editing. Offline concurrency needs an HLC/Lamport timestamp for
  intuitive tiebreaks.
- **Dangling references are tolerated, not prevented.** Correctness depends on **every** read,
  delta, and aggregate path applying the referential filter; a path that forgets it will ship
  orphan data. This is a discipline cost spread across the read layer.
- **Dormant data accumulates** between compactions (dead entities' dependent rows are retained
  for possible redo until `H` passes them).
- **Set fields must use the add/remove path,** not whole-list replace, or concurrent edits to
  e.g. `parents` will still collide.
- **`changes` loses static typing** (it's a generic dict); writes must validate keys against
  the target struct.
- **Migration is non-trivial:** existing snapshot `_log` chains must be diffed into
  `ChangeOp`s once, and the read layer must gain referential filtering.

---

## 6. Implementation map (`panoptic/core/databases/data/`)

- **`models.py`** — `ChangeOp` (generic partial-diff log row: `entity_type, entity_key,
  commit, op, changes:dict`); `Commit` gains `author` (`active` is the enabled bit).
- **`create.py`** — single `entity_log` table + result tables (no per-entity `_log`);
  `LOGGED_ENTITY_META` (shared spec metadata); `GENESIS_COMMIT_ID = 0`. No migrations: the
  data DB is created fresh at the current schema (`version=1`, `migrations={}`).
- **`resolver.py`** — `ENTITY_SPECS`, `encode_key`/`decode_key`, `diff_changes` (write-side
  minimal diff), and `resolve` (enabled-ops fold with causal existence + LWW + OR-Sets).
- **`data_writer.py`** — `apply_commit` (diff → `ChangeOp`s, tag-value → junction expansion,
  revertable cascade deletes, materialize touched); `set_commit_active` (non-sequential
  toggle → re-resolve touched); `compact(horizon)`; structural API unchanged; `entity_log`-
  aware structural GC. Genesis (commit 0) is always-enabled via the op query (no commits row).
- **`data_reader.py`** — result-table reads unchanged; `get_delta` gains referential filtering
  (drops value rows of non-alive properties); `get_commits` hides genesis.

Tests: `test/test_data_db.py` — the original structural/logged suite **plus** causal-existence
(undo-creation-with-later-update), non-sequential middle undo, per-field collateral, OR-Set
parents, multi-user revert-property-creation-with-dependent-data, and compaction baseline.
All green.

Known follow-ups (not blocking): thread `author` from the undo/redo routes for real per-user
stacks; extend referential filtering to tags of a dead list and to the point-read paths;
provenance/runner-up optimization (revert-complexity note §6) and a background compaction
watermark (design note §10).

## 7. Non-goals

- A general document/OT/CRDT text-merge engine — resolution is per-cell LWW + OR-Sets, nothing
  finer (no intra-string merge).
- Unlimited/infinite undo history (explicitly traded away for the bounded cost in §2.6).
- Automatic cross-entity reconciliation on undo (explicitly rejected in §2.5 to avoid
  reverting others' work).
