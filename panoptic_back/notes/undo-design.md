# Undo design — a model with no bad edge cases

Companion to `undo.md` (audit of the current system). Scope: **properties,
property_groups, tags, property values** (incl. tag assignments and tag parents).
Immutable-after-create fields (property `dtype`, `mode`, value storage mode) are stored
once on the entity and excluded from the whole mechanism. User management stays out of
the DB: each client remembers the commit ids it created and toggles those — the engine
only needs "toggle commit N", which is already user-agnostic.

## 1. The one invariant everything follows from

> **The visible state of the database is a pure function of the *set of active
> commits*.** `state = fold(log, active_set)` — nothing else.

Every bad edge case in the audit is a violation of this invariant:

- *Full-row update logs* (BUG 4) make state depend on which commit happened to copy
  which field — the log entry captures more than the user's intent.
- *Write-time set diffs* (EDGE 1) bake "what was visible when the user clicked" into the
  log, so toggling an older commit changes the meaning of later entries.
- *Cascade rows / stale rows* (BUG 1, BUG 2) store *derived* consequences as if they
  were facts, so the derived data goes stale when the underlying commit is toggled.
- *Two-commit merge* makes one user action two toggle units.

So the design rules are:

1. A log entry records **only the user's atomic intent**, at the finest granularity that
   intent has (one field, one set-element, one existence flag).
2. **Nothing derived is ever logged.** Referential consequences (tag dies with its
   property, assignment dies with its tag) are *computed at read/materialize time*.
3. One user action = **one commit**, however many ops it contains.

With those rules, toggling any subset of commits, in any order, always yields one
well-defined, referentially consistent state — non-sequential undo stops being a special
case at all.

## 2. The log: three primitive op kinds

Single append-only table (typed per-entity log tables work too, this is just clearer):

```sql
CREATE TABLE ops (
    commit_id   INTEGER NOT NULL,            -- monotonic, allocator-style
    entity_type TEXT    NOT NULL,            -- 'property'|'property_group'|'tag'|'value'
    entity_id   TEXT    NOT NULL,            -- tag id, property id, or value key
                                             --   (property_id:instance_id / :sha1 / :file_id)
    field       TEXT    NOT NULL,            -- 'exists'|'name'|'color'|'group_id'|'value'|
                                             --   'parents'|'tags' ...
    element     INTEGER,                     -- only for set-fields: the member (tag id)
    op          TEXT    NOT NULL,            -- 'create'|'delete'|'set'|'add'|'remove'
    value       JSON,                        -- only for 'set'
    PRIMARY KEY (entity_type, entity_id, field, element, commit_id)
);
CREATE INDEX idx_ops_commit ON ops (commit_id);
```

plus `commits(id, source, timestamp, active)` exactly as today. Three register kinds,
each with a trivial fold:

| Register | ops | fold over **active** entries |
|---|---|---|
| **Existence** — `(type, id, 'exists')` | `create` / `delete` | alive iff the highest active commit_id entry is `create`; **no active entry = does not exist** |
| **Scalar (LWW)** — `(type, id, field)` | `set` | value of the highest active commit_id entry; no active entry = unset/default |
| **Set (per-element LWW)** — `(type, id, field, element)` | `add` / `remove` | element ∈ set iff the highest active entry *for that element* is `add` |

What uses what:

- `property`: existence + scalars `name`, `group_id`. (`dtype`/`mode` immutable, on the
  entity row, never logged.)
- `property_group`: existence + scalar `name`.
- `tag`: existence + scalars `name`, `color` + set `parents` (elements = tag ids).
- `value` (scalar property): scalar `value`. "Clear value" = `set NULL` (an explicit op
  — clearing is intent like any other, never a row deletion).
- `value` (multi-tag property): set `tags` (elements = tag ids).

Why commit_id is a valid LWW arbiter: single SQLite writer ⇒ commit ids are allocated in
strict wall-clock commit order, and toggling never reorders them. The fold needs no
timestamps and no replay loop — per register it's just `MAX(commit_id) WHERE active`.

## 3. Derived visibility instead of cascades

Deleting or undoing-the-creation-of a parent never writes ops for its dependents.
Visibility is computed:

```
visible(property_group) = alive(group)
visible(property)       = alive(property)                  -- groups do NOT gate properties
visible(tag)            = alive(tag) AND visible(its property)
visible(parent edge)    = both tags visible                -- else edge filtered, kept latent
visible(value)          = visible(property)
visible(tag in a value) = tag visible                      -- else element filtered, kept latent
property.group_id       = NULL when the group is not visible (latent, restored on redo)
```

This is the move that deletes the two worst bug classes:

- **Undo of a create** (`BUG 1` + `BUG 2`): toggling the commit that created tag T flips
  one existence register. Every assignment, parent edge and child referencing T becomes
  *invisible by derivation* — and reappears identically on redo, because the underlying
  registers were never touched. There are no dangling references **by construction**:
  the read layer cannot show an edge to an invisible node.
- **Tag/property delete needs exactly one op** (`existence ← delete`). Undo of that
  delete restores the whole subtree, including values other users wrote before the
  delete, with zero cascade bookkeeping. The current system's cascade rows (which are
  derived data masquerading as intent) disappear entirely — and with them BUG 5
  (children's `parents` dangling after tag delete: the edge is now just filtered while
  the parent is dead, restored if the parent comes back).

## 4. Materialized current state (cache, not truth)

Folding registers on every read is too slow, so keep the current-state tables — but
demoted to a **cache of `fold(log, active_set)`**, never written directly:

- Cache rows carry `sequence` for delta-sync; a register folding to "nonexistent /
  invisible" is materialized as a **tombstone row with a fresh sequence** (this is the
  audit's BUG 1 fix, but here it's structural: absence is a first-class fold outcome,
  not a skipped case).
- Two bits per row: `alive_own` (existence fold) and `visible` (own ∧ ancestors), so
  visibility flips don't have to re-fold descendants' registers — they only AND a bit
  down the dependency DAG: `group → (group_id display)`, `property → tags, values`,
  `tag → parent edges, value elements`.

**Recompute scope on toggling commit C** is exact and cheap:

1. Re-fold every register named in C's ops (`SELECT … FROM ops WHERE commit_id = C`).
2. For each *existence* register whose visibility flipped, propagate the `visible` bit
   to dependents (one indexed pass per dependent table).
3. Bump `sequence` on every cache row that changed, tombstones included.

Same code path for undo and redo; toggling is idempotent; toggles commute. A
`rebuild_cache()` that re-folds everything from scratch doubles as migration tool and
as an invariant checker in tests (`assert incremental == rebuild` after random toggle
sequences — property-based testing falls out for free).

## 5. The write API: capture intent, not state

- **Scalars:** UI sends only the fields the user edited → one `set` op per edited field.
  Never send untouched fields. This kills BUG 4 (masking): B's recolor logs only
  `color`, so undoing A's rename actually reverts the name — the registers are
  independent.
- **Sets (tag assignments, parents):** UI sends `add`/`remove` element ops **diffed
  against the client's own view**, not against DB state — and *redundant ops are
  welcome*: if the user re-asserts a tag that's already present, log the `add` anyway.
  Under per-element LWW a redundant `add` re-pins the element at a newer commit, so a
  later undo of the *original* add no longer removes something this user explicitly
  confirmed. (This fixes the current system's EDGE 2, where no-op writes log nothing and
  user intent evaporates.)
- **Creates:** allocator ids (never reused — already true today) + `create` op + initial
  `set`/`add` ops, all in one commit.
- **Compound user actions** (merge, "delete group and ungroup its properties", batch
  tagging) = one commit. The engine has no concept of multi-commit actions, so no
  group_id machinery and no partial undo.

## 6. Tag merge, walked through

`merge(losers → winner)`, one commit C_m, only primitive ops:

```
for each multi-tag value containing a loser L:   remove L,  add winner (redundant-ok)
for each tag with a loser L in parents:          remove L,  add winner
winner.parents:                                  add each loser-parent not already there
each loser:                                      exists ← delete
```

Why every interleaving now behaves:

- **Undo C_m** re-folds exactly C_m's registers: losers alive again; every
  `remove L` from C_m loses to the older `add L` → losers' assignments restored; every
  `add winner` from C_m disappears — **unless the image already had the winner from an
  older commit, in which case it correctly keeps it**. Exact, atomic un-merge. (The
  current two-commit merge restores the tags but leaves all values pointing at the
  winner.)
- **Post-merge edits survive sensibly:** user C removes the winner from an image after
  the merge, then someone undoes the merge → the loser returns (its removal was C_m's),
  the winner stays removed (C's `remove` outranks every `add`). Each tag's history is
  its own register; nothing is entangled.
- **Merge after merge** (B→A, then C→A, undo the first): independent registers,
  independent undo. **Merge a tag whose property is later deleted**: all latent,
  restored if the property delete is undone.
- **Drift is impossible** because C_m's `remove`/`add` ops mean the same thing under any
  active set — they are not diffs against a vanished snapshot.

## 7. Undo/redo mechanics (per-user, no DB user model)

- Client keeps its own stack of commit ids it created (the engine returns the id on
  every write). Undo = `toggle(my_ids LIFO)`, redo = inverse. Two users toggling
  interleaved commits is the *normal* case, not a special one.
- The server only validates: commit exists, desired state differs (else no-op 200).
- `source` on commits stays as a debugging label; nothing reads it.
- Delta-sync unchanged: toggle bumps `sequence` on every changed cache row, tombstones
  included, so other clients converge without knowing a toggle happened.

## 8. Edge-case ledger

Every edge case from the audit, and its status here:

| Edge case (audit) | Status in this design |
|---|---|
| Undo of create leaves stale row (BUG 1) | Gone — absence is a fold outcome, materialized as tombstone |
| Dangling refs after undo-of-create (BUG 2) | Gone — visibility derived, never stored |
| Full-state update masking (BUG 4) | Gone — per-field registers |
| Tag delete leaves children's parents dangling (BUG 5) | Gone — edges filtered while parent invisible, latent restore |
| Diff-base drift on junctions (EDGE 1) | Gone — ops are intent, valid under any active set |
| No-op writes lose user intent (EDGE 2) | Gone — redundant element ops are logged and re-pin |
| Update-after-delete resurrects (EDGE 3) | Gone — a `set` on a dead entity changes a scalar register but existence stays `delete`-folded; entity stays dead until the delete is undone |
| Two-commit merge / partial undo | Gone — one commit per user action, no groups needed |
| Value "deletion" undefined (BUG 6) | Gone — clearing is an explicit `set NULL` op |

Two semantics that remain — *decided*, not accidental:

- **Redo of an old commit can reapply old intent.** Undo `+a`, someone clears the
  visible tags (logs removes for what they saw — not `a`), redo `+a` → `a` is present
  after the "clear". This is correct under the model's reading: ops are explicit intent,
  and no later op ever said "remove a". If product wants "clear beats everything", make
  clear a UI affordance that logs removes for *all* elements with any active `add` —
  expressible inside the model, no engine change.
- **Latent parent edges can re-form a cycle.** c2 removes A→B, c3 adds B→A (valid then);
  undo c2 → both edges active. Cycles are prevented at *write* time, but toggles can
  recombine old edges. The fold needs one deterministic tie-break: when computing
  visible parent edges, walk edges in ascending commit_id and drop any edge that would
  close a cycle. Deterministic, order-independent for the user, and the dropped edge is
  latent — it returns when the conflict is toggled away.

## 9. Why this structure is strictly better

The current system already wants to be this — `set_commit_active` + replay is the right
shape, junction tables are already per-element, `OP_STAMP_DIFF` hints at field diffs.
But it stores three things that aren't pure intent: full-row updates, write-time-diff
meanings, and cascade rows; and it treats absence as a skippable case. Each of those is
one audited bug class.

This design's guarantees, each traceable to one structural choice:

1. **Determinism** — state is `fold(log, active_set)`; toggles commute; undo/redo are
   exact inverses; property-testable by comparing incremental vs full rebuild.
2. **No referential breakage, ever** — visibility is computed, so the read layer is
   incapable of showing a dangling reference; nothing to cascade, nothing to forget.
3. **Per-user undo fidelity** — a commit touches exactly the registers its user changed,
   so toggling it affects exactly that user's contribution (field-level, element-level).
4. **Compound actions are atomic** — merge included, with exact restoration.
5. **Locality** — toggle cost is proportional to the commit's op count plus the
   visibility fan-out of flipped existences; nothing global.
6. **Same external contracts** — sequence/delta-sync, allocator ids, single-writer
   SQLite, soft tombstones for sync all carry over; the change is what the log *means*,
   not the infrastructure around it.

Migration note: the existing logs can be transcribed (full-row update → `set` ops for
each non-null field; junction CREATE/DELETE → `add`/`remove`; cascade rows → dropped,
they're derivable), so history survives. But given undo history is short-lived in
practice, "new model for new commits, freeze old history" is also acceptable.

## 10. Complexity at scale (millions of value rows)

Sizes used below: properties **P ≈ 10²**, groups **G ≈ 10¹**, tags **T ≈ 10³–10⁴**,
instances ≈ 10⁶–10⁷, value + junction rows **V ≈ 10⁶–10⁸**. The split that matters:
the *gating* entities (P, G, T) are tiny and always fit in memory; only values/junctions
are huge — and nothing depends on them.

### The unit cost: folding one register

```sql
SELECT op, value FROM ops
WHERE entity_type=? AND entity_id=? AND field=? AND element IS ?
ORDER BY commit_id DESC          -- walks the PK index backwards
```

Walk from the top, return the first row whose commit is active (keep the disabled-commit
set in memory — `commits` is small). So a fold is **one index descent, O(log |ops|) ≈
20–30 page touches at 10⁸ rows, then usually 1 row read** — it stops at the first active
entry, it does not replay history (the current `re_compute` folds the *full* per-PK
history every time). Worst case O(disabled entries stacked on that one register), which
is bounded by that user's undo depth on that field, not by DB size.

### Small writes — the everyday operations — are size-independent

| Operation | Work | Cost vs V = millions |
|---|---|---|
| set one value on one image | 1 op insert + 1 fold + 1 cache upsert + sequence | **O(1)** — 3–5 index ops, µs–ms |
| tag/untag one image (e elements) | e × (insert + fold + cache upsert) | **O(e)**, e is 1–5 |
| rename property / recolor tag / move to group | 1 op + 1 fold + 1 cache row | **O(1)** |
| change tag parents | per-element, + cycle walk over that property's visible tag DAG | **O(e + T_prop)** — tags only, never values |
| undo/redo a commit with c ops | c folds + c cache upserts | **O(c)** — undo costs what the write cost, which is optimal |

Identical order to the current system's write path (log append + upsert); the register
model adds no per-write overhead. Storage is actually *smaller* per edit: one
field-level op row vs a full entity row per update.

### The one size-dependent operation: existence flips

Deleting / undoing-the-create of a tag or property changes the visibility of its **d**
dependents (d = assignments of that tag, or value rows of that property — possibly
millions). Two strategies:

1. **Materialized `visible` bit on big tables (rejected):** toggle = O(d) row updates +
   O(d) sequence bumps. At d = 10⁶ that's seconds inside SQLite's single write lock,
   and a million-row delta for every sync client. And it's symmetric: the undo pays it
   again.
2. **Read-side derivation for big tables (the design choice):** never store `visible` on
   values/junctions — only their own fold (`alive_own`). Visibility = own bit ∧
   membership of `property_id`/`tag_id` in the in-memory visible sets of P and T (hash
   lookups during streams the reader is already iterating; aggregate SQL joins the tiny
   tags/properties tables instead). Then **an existence flip is O(1)**: one op row, one
   tombstone cache row for the parent, one sequence bump. Delta-sync ships *one* row;
   clients already hold all tags/properties and apply the same derivation rule locally.

Rule of thumb: **materialize `visible` only where fan-out is bounded by T** (tags gated
by their property, parent edges) — flipping a property's visibility touches at most its
tags. The million-row tables never gate anything, so they never need the bit.

This is also where the design structurally beats the current system: undoing
"create property" after others wrote a million values under it is O(1) here; a *fixed*
current system (cascade-on-undo per `undo.md` BUG 2) would have to visit all d rows on
every toggle.

### Proportional cases (can't do better, don't need to)

- **Batch action** (tag 100k images in one commit): write O(100k) op rows in one
  transaction (~1s in SQLite), undo/redo O(100k) folds. Undo cost ≈ original action
  cost — proportional to intent, optimal.
- **Merge** where losers have d assignments: O(d) ops written once, O(d) to undo. Same
  order as the merge itself. Note merge *writes* ops per affected row, so at write time
  it scans the loser's junction rows via the `tag_id` index — O(d), unavoidable since
  retargeting is per-row intent.
- **`rebuild_cache()`**: O(|ops|), offline/migration/testing only.

### Growth and hygiene

- `ops` grows with edit count, not with V. Indexes: the PK (register folds) +
  `idx_ops_commit` (toggle scope) + `tag_id` on junction cache (merge, counts). All
  standard B-trees; nothing scans the big tables for undo purposes.
- Unbounded history can be compacted: registers older than a horizon (or whose commits
  are permanently active) can be squashed to one `set`/`add` row per register without
  changing any fold result — a safe vacuum, since fold only ever reads down to the first
  active entry.
