# Revert Complexity & Delta-Since-Sequence — Analysis & Target

Companion to `versioning_replay_analysis.md`. Focus: *what does one revert cost as a
function of the action being reverted*, and *how cheaply can the DB report the delta since
a sequence number*. Goal for both: cost proportional to the size of the change, nothing else.

---

## 1. Cost model

Terms for the commit being reverted:

| symbol | meaning |
|--------|---------|
| `m`  | rows the commit itself wrote = **its own log rows** ("commit footprint") |
| `h_i`| history depth of touched PK *i* = total log rows that PK has across **all** commits |
| `H`  | `Σ h_i` over the `m` touched PKs |
| `C`  | total number of commits in the project |
| `Sc` | number of logged schemas (currently 8) |

The inherent lower bound for reverting an action is **O(m)** — you must re-materialize
exactly the rows the action changed, no more. Anything above `O(m)` is overhead.

---

## 2. What one revert costs **today**

Path: `set_commit_active` (`data_writer.py:275`) → per-schema `re_compute`
(`entity_schema.py:903`).

```
set_commit_active(X):
  COMMITS.get(tx)                      # O(C)  — fetch ALL commits to build `disabled`
  for each of 8 schemas:
     get_log(X)                        # O(m_schema) rows this commit touched in schema
     _get_log_by_pks(touched_pks)      # O(H_schema) — FULL history of each touched PK
     fold + upsert                     # O(H_schema) fold, O(m_schema) writes
```

**Per-revert cost = O(C + Sc + H) reads, O(m) writes.**

Two multipliers make this far above the `O(m)` floor:

- **`H` (history depth).** Reverting a commit re-reads and re-folds the *entire* edit
  history of every entity it touched — not just this commit's contribution. Toggling a
  one-field rename of a property that has been edited 500 times costs ~500 log reads, not 1.
- **`C` (commit count) + `Sc` fixed overhead.** Every revert fetches all commits and probes
  all 8 log tables, even to undo a single-row edit. A trivial revert is never cheap.

So today: **cost ≈ O(C + Σ history-depth of the footprint)** — it grows with project age
and with how heavily the touched entities were previously edited, both of which are
irrelevant to the size of the thing being undone.

---

## 3. Cost per action (current vs. optimal)

`m` below is the action's footprint; `h` an average per-PK history depth.

| Action reverted | footprint `m` | **current cost** | optimal |
|---|---|---|---|
| Rename a property | 1 | O(C + h_P) | **O(1)** |
| Set 1 instance/sha1 value | 1 | O(C + h_v) | **O(1)** |
| Change a tag's parents | 1 (+ rewritten children) | O(C + h_T) | **O(1..#children)** |
| Add tag to N instances | N junction rows | O(C + N·h) | **O(N)** |
| Tag merge (main+children+all values of removed tags, +delete) | O(#affected tags + #affected values) | O(C + Σh) ; **×2 commits, non-atomic** | **O(m), 1 commit** |
| Delete property with V values (cascade) | O(V) | O(C + Σh) | **O(V) = O(m)** |

Note the delete-cascade row: restoring V values inherently costs `O(V)`, so `O(m)` is
already optimal there — the win is dropping the `×h` and `+C`. Everywhere else the current
cost is *super-linear* in what the user actually did.

---

## 4. Target: revert in O(m), no `h`, no `C`

The crucial observation: **the existing `_log` tables already contain everything needed for
an `O(m)` revert of the head commit — no schema change required.** To undo commit `X` you do
not need to refold full history; you need, per touched PK, the state *immediately before X*.

### 4a. Head revert = "previous log entry per PK" (linear undo)
For a linear history (the recommended model — see companion note), disabling the head commit
`X` yields, for each PK it touched:

- the log row with the greatest `commit_id < X` → the pre-X state (an UPDATE/CREATE), **or**
- **no such row** → the PK was *created* by `X` → **tombstone it** (this is also the fix for
  the P1 stale-row bug).

```sql
-- one indexed query, batched over the touched PKs
SELECT l.* FROM <t>_log l
JOIN (SELECT <pks>, MAX(commit_id) AS mc
      FROM <t>_log
      WHERE commit_id < :X AND <pk> IN (:touched)
      GROUP BY <pks>) m
  ON <pk-join> AND l.commit_id = m.mc;
```

This is `get_latest_logs` bounded by `commit_id < X`, served by the existing
`idx_<t>_log_entity (pks, commit_id)` index (`entity_schema.py:385`). Cost **O(m)**, with
no dependence on `h` or `C`. Redo (`re-enable X`) is symmetric: state = the log rows *at* X
= `get_log(X)` (`entity_schema.py:681`), also **O(m)**.

Also drop the two fixed overheads: don't `COMMITS.get()` the whole table (a linear model
needs only the HEAD pointer), and only touch schemas that `X` actually wrote (skip empty
ones instead of probing all 8).

### 4b. Optional: explicit inverse-delta journal
If you want revert to be a pure data replay with zero query logic, persist per commit the
**before-image** of each row it changed (the writer already reads `existing` before writing
— `data_writer.py:365,371`). Revert = bulk-upsert the before-images; redo = bulk-upsert the
after-images (which is just the current `_log`). Both **O(m)**. This duplicates some data but
makes revert a dumb, index-free bulk write — attractive if reverts must be very fast/large.

### 4c. Arbitrary (non-linear) revert
Reverting a *non-head* commit while later commits touched the same PKs cannot be done from a
single before-image; it needs either a bounded refold or reconciliation. Keep this out of
scope (companion note recommends linear-only undo). If ever required, bound `h` with periodic
**checkpoints** (materialize state every K commits so a fold reads ≤ K rows/PK), turning the
refold into `O(m·K)` with K constant.

---

## 5. Delta since a sequence number

### How it works now
Every logged/structural table has a `sequence` column + `idx_<t>_sequence`
(`entity_schema.py:341`), fed by one global monotonic counter bumped per transaction
(`_exec_get_sequence`, `data_writer.py:585`). `get_since(S)` is `WHERE sequence > S` per table
(`entity_schema.py:673`) → **O(rows changed since S)** via the index. Structurally this is
already optimal: the delta is exactly the rows whose `sequence` advanced.

A revert takes a fresh sequence and re-stamps the rows it re-materializes, so a client that
saved the pre-revert sequence gets precisely the reverted rows on its next `get_since`. Keep
this design.

### The one thing to fix: don't over-stamp
`re_compute` re-upserts **all** touched PKs and bumps their `sequence` even when the
refold produced a value identical to what was already there. That inflates the delta —
clients re-fetch rows that did not actually change. With the `O(m)` head-revert (§4a) you
already touch only rows whose value flips; go one step further and **only bump `sequence`
for rows whose materialized value actually changes** (compare before upsert, or rely on the
before/after images differing). Then:

> **delta-since-S == exactly the set of rows whose visible value changed since S**, and both
> "compute the revert" and "report its delta" are `O(m)`.

### Tombstones keep deletes visible in the delta
Because reverts (and the P1 fix) *tombstone* rows (`operation=DELETE` with a new sequence)
rather than hard-deleting them, `get_since` naturally carries "this row is now gone" to
clients. A hard delete would be invisible to delta-sync — don't hard-delete logged rows on
revert.

---

## 6. Summary

- Today one revert costs **O(C + Σ history-depth of the touched entities)** — super-linear
  in the action size, and it grows as the project ages. The `×h` and `+C` factors are pure
  overhead.
- The **floor is O(m)** (the action's footprint), and it is reachable **with no schema
  change**: for head/linear undo, materialize each touched PK from its *previous* log entry
  (or tombstone if none) instead of refolding full history; skip the all-commits fetch and
  the empty-schema probes.
- **Delta-since-sequence is already O(delta)** via the `sequence` index; the only change
  needed is to stop bumping `sequence` on rows the revert didn't actually change, so the
  reported delta is minimal and exact. Tombstone (never hard-delete) so removals stay visible.
