# Non-Sequential, Multi-User Selective Undo — Design

Companion to `versioning_replay_analysis.md` and `versioning_revert_complexity.md`.

Requirement: **any user can undo their own commit regardless of position in the log**,
without reverting others' concurrent work, with race/collateral effects **as small as
physically possible**.

This rules out both the linear-stack optimizations (§4a/§4b of the complexity note) and the
current entity-snapshot fold. The right model is *selective undo over a per-cell,
enabled-set-driven state*.

---

## 1. Two independent requirements, two design choices

1. **Non-sequential / order-independent undo** → *state must be a pure function of the set
   of enabled commits*, never of their order. Undo = flip a commit's `enabled` bit and
   re-resolve only the affected cells. (The current `re_compute` already aims for this — a
   fold over a `disabled` set — but at entity-snapshot granularity, which is what causes the
   collateral.)
2. **Minimal collateral between users** → *the unit of conflict must be as fine-grained as
   possible*. Today the unit is a whole row (a whole `Property`, a whole `Tag`), so two users
   editing different fields of the same property collide, and undoing one reverts the other.
   Shrink the unit to a **cell** (one column, or one set-element) and collisions only happen
   when two users truly write the *same cell*.

The whole design is: **decompose every mutation into per-cell ops, and materialize each cell
as the winning *enabled* op for that cell.**

---

## 2. The cell taxonomy (what "a cell" is per entity)

| Entity | Cell | Resolution type |
|---|---|---|
| Property | each scalar column (`name`, `dtype`, `mode`, `tag_list_id`, `property_group_id`) | **LWW register** |
| Tag | `value`, `color` (scalars) | **LWW register** |
| Tag | `parents` (set of tag ids) | **OR-Set** (per-element add/remove) |
| PropertyGroup | `name` | **LWW register** |
| instance/sha1/file value | the single value at (property, key) | **LWW register** (one cell) |
| tag assignment (`instance_tag_values`, `sha1_tag_values`) | each (key, property, tag) membership | **OR-Set element** |
| existence of any entity | a synthetic `__alive__` cell | **LWW register (bool)** — CREATE writes true, DELETE writes false |

Note how much is **already fine-grained** in the current schema: the junction tables are
per-(key,property,tag) rows with CREATE/DELETE ops — that is exactly an OR-Set. The value
tables are one cell each. **Only `properties` / `tags` / `property_groups` need
decomposing** from whole-row snapshots into per-column cells. Limited scope.

---

## 3. The op log

One append-only operation table (or keep per-entity `_log` tables, but keyed by cell):

```
op(
  commit_id     INTEGER,   -- groups a user action; carries author + timestamp via commits table
  entity_kind   TEXT,      -- 'property' | 'tag' | 'group' | 'value' | 'tag_assign' ...
  entity_id     …,         -- pk(s) of the entity
  cell          TEXT,      -- column name, set-element key, or '__alive__'
  op_type       INTEGER,   -- SET | ADD | REMOVE
  value         JSON,      -- payload for SET/ADD
  sequence      INTEGER    -- global monotonic, for delta-sync
)
-- index (entity_kind, entity_id, cell, commit_id)
```

`commits(id, author, timestamp, enabled, group_id)` — `enabled` replaces today's `active`.

### Materialized state per cell = resolve(enabled ops for that cell)
- **LWW register:** the enabled op with the greatest `(timestamp, commit_id)` wins. (For a
  centralized project DB, `commit_id` alone is a fine total order; add a Lamport/HLC clock
  only if offline concurrent editing is real — see §7.)
- **OR-Set element present** iff it has an enabled ADD not shadowed by a later enabled REMOVE
  (add-wins or timestamp-wins — pick one policy, document it).
- **`__alive__`:** LWW bool over enabled CREATE/DELETE writes. Entity is visible iff it
  resolves to true.

State is a **pure function of the enabled set** → fully order-independent → non-sequential
undo works by construction.

---

## 4. Undo / redo semantics

- A user action = one `commit_id` (a bundle of cell-ops) with `author = that user`.
- **Undo** = pick the greatest still-enabled `commit_id` **for that author**, set
  `enabled = 0`, and re-resolve only the cells that commit wrote.
- **Redo** = the symmetric re-enable.
- Each user effectively has their **own undo stack** (their commits ordered by time), but
  undo is *selective*: disabling user A's commit 5 is valid even though users B/C made
  commits 6, 7, 8 afterward — because state doesn't depend on order.

### What actually changes on an undo of commit X
Only the cells X touched, and among those only the ones where X's op was the current winner.
For each such cell, re-resolve from the remaining enabled ops → new winner (or the cell
disappears if none). **Cells X didn't touch are never read or written.** That's the source
of "no collateral."

**Cost:** O(cells touched by X × ops-per-cell). Common case O(m) (scan a cell's ops newest-
first until the first enabled one — cheap when few commits are disabled). Worst case bounded
with periodic checkpoints if needed (see complexity note §4c). Each re-resolved cell gets a
fresh `sequence` → delta-sync reports exactly those cells (§6).

---

## 5. Race analysis — what collides and what doesn't

| Scenario | Outcome |
|---|---|
| A renames property, B moves it to a group | **No conflict** — different columns/cells. |
| A tags instance i with tag X, B tags i with tag Y | **No conflict** — different OR-Set elements; both present. |
| A and B tag different instances | **No conflict** — different rows. |
| A adds parent P1 to tag T, B adds parent P2 | **No conflict** — OR-Set, both parents present. |
| A and B set the **same** scalar cell (same property name, or same value cell) | **Race** — LWW; undo of the winner falls back to the other's value. *Inherent & minimal.* |
| A deletes tag T, B renames T | `__alive__` = false wins → T hidden; B's rename is **dormant** (preserved, reappears if the delete is undone). Not lost. |
| A undoes *creation* of tag T while B's enabled edits reference T | T's `__alive__` → false. B's edits dormant. Dangling refs (a child's `parents`, assignments) are **filtered at read** (§8), not deleted. |

The only true races are two users writing the *same cell*; everything else composes. That is
the physical minimum.

---

## 6. Delta-since-sequence

Unchanged in spirit from today, and still O(delta):
- Materialized cell/row tables keep a `sequence` column + index.
- Applying an op, or re-resolving a cell after an undo, stamps the changed cell with a fresh
  `sequence`. **Only cells whose resolved value actually changed are re-stamped** (don't bump
  a cell whose winner is unchanged) → the reported delta is minimal and exact.
- Deletions surface as `__alive__ = false` (a tombstone with a new sequence), so removals are
  visible to `get_since` — never hard-delete on undo.

`get_since(S)` = `WHERE sequence > S` per table → the client receives precisely the cells
that changed since it last synced, whether the change came from another user's edit or from
anyone's undo.

---

## 7. Ordering / clocks

- If commits are serialized by the single project DB (each `apply` gets a global
  `commit_id`), that id is a sufficient **total order** for LWW tiebreaks — no vector clocks
  needed.
- If clients can edit **offline** and sync later, two commits can be *concurrent*; use a
  **Hybrid Logical Clock** (wall-clock + counter) per commit as the LWW timestamp so
  concurrent same-cell writes resolve deterministically and intuitively (latest wall-clock
  wins, counter breaks ties). Everything else in the design is unchanged.

---

## 8. Referential integrity — the one genuinely hard part

Cross-entity references (`tag.parents → tag`, `property.tag_list_id`,
`property.property_group_id`, `assignment.tag_id → tag`) can dangle after a selective undo
because the referenced entity's `__alive__` flipped to false while a referencing cell stays
enabled. **Do not reconcile by editing the referencing cells** — that would revert another
user's work, violating the requirement.

Instead: **tolerate dangling refs and resolve them at read time.**
- Reads join against currently-alive entities and drop/omit references to non-alive ones
  (a child's `parents` list filters out ids whose tag isn't alive; a tag assignment to a
  non-alive tag isn't returned).
- The referencing op is never deleted, so if the entity is later redone, the reference
  reappears automatically.

This keeps undo O(m), never blocks, never touches other users' cells, and is
self-healing on redo. The cost is read-time filtering (cheap, and mostly already implicit in
how tags/values are read).

---

## 9. Scope of change from today

- **Keep:** the junction tables (already OR-Sets), the value tables (already single cells),
  the `sequence`/`get_since` delta mechanism, the commit table (rename `active`→`enabled`,
  add `author`).
- **Change:** decompose `properties` / `tags` / `property_groups` writes into per-column
  cell-ops; add the `__alive__` existence cell; make resolution per-cell (LWW / OR-Set)
  instead of the entity-snapshot `merge_logs`; make undo select by `(author, max enabled
  commit_id)` and re-resolve only touched cells.
- **Add:** read-time referential filtering (§8); optionally HLC timestamps (§7) and
  checkpoints for worst-case bounds.

---

## 10. Bottom line

- **Non-sequential, per-user selective undo is fully supported** by making materialized state
  a pure function of the *enabled set*, resolved **per cell**.
- **Collateral is minimized to the physical floor:** users only ever interfere when they
  write the *same cell*; disjoint edits (different columns, different tags, different
  instances) never conflict and never get reverted by someone else's undo.
- **The residual races** (same-cell LWW; edits dormant under a deleted parent) are inherent
  to concurrent editing and are handled non-destructively (nothing is lost; redo restores).
- **Delta-sync stays O(delta)** and correctly reports both edits and undos as changed cells.
- **The real engineering cost is not the undo** — it's (a) decomposing property/tag edits to
  cell granularity and (b) read-time referential filtering. Both are bounded and local.
