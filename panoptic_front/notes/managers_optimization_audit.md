# Managers Optimization Audit — Group / Filter / Sort over ColumnStore

Date: 2026-05-30. Branch: `opti`.

Scope: `src/core/GroupManager.ts`, `src/core/FilterManager.ts`, `src/core/SortManager.ts`
reading from `src/data/columnStore.ts`. This is a **current-state audit** — the codebase has
already absorbed most of Phase 0/1 from [[group_manager_redesign_plan]],
[[group_tree_structure_redesign]] and [[managers_1m_optimization]], so those notes now
over-state the problem. This note records what is *actually* left, plus a direct answer to
the "map every value to a reproducible group id / would hashing kill performance" question.

---

## 0. TL;DR

- **The group-id question:** the current `GroupValueIndex` (nested-Map trie + counter,
  persistent across rebuilds) is already the right structure and is **already reproducible
  within a session**. Hashing would **not** destroy performance — id assignment is
  *per-group* (thousands), not *per-slot* (millions). But hashing buys you nothing you don't
  already have unless you need **cross-session** stability, and then the correct fix is to
  persist the **value path**, not a hash (zero collision risk). See §2.
- **Three verified, low-risk wins available now:**
  1. Delete `SortManager.result.order` — it is a 1M-key object rebuilt every sort and
     **read nowhere** (`SortManager.ts:382,445`). Pure waste. §5.1
  2. Make `GroupManager.updateSelection` actually incremental — it currently does **two
     O(n) passes** (rebuild the whole `imageToGroups`, re-sort every group's slots) on every
     incremental edit (`GroupManager.ts:444-454`). §3.1
  3. Fold date filtering into the Float64 fast path — it allocates **one `Date` per slot**
     for nothing (`FilterManager.ts:220-230`). §4.1
- **Biggest structural win still open:** integer cursors + descriptor lines in TreeScroller
  (still allocates ~2M `ImageIterator`s per `computeLines`, `TreeScroller.vue:205-262`).
  Tracked in [[group_tree_structure_redesign]] Phase 2/3 — not done.
- **Biggest algorithmic win still open:** wire the **tag inverted index** (already built by
  `columnStore.requireTagInverted`, `columnStore.ts:343`) into FilterManager's
  `containsAny`/`containsAll`, turning O(n × tags) into O(result). §4.3

---

## 1. What is already done (do not re-propose)

The older notes assume an un-optimized baseline. Reality on `opti`:

| Optimization | Status | Evidence |
|---|---|---|
| Slot-based groups (`Group.slots: number[]`) | ✅ done | `GroupManager.ts:42` |
| `orderedIds: Int32Array` (DFS instance-id order) | ✅ done | `buildOrdinalRanges` L398-423 |
| `imageToGroups: Map<id, Set<groupId>>` (O(1) delete) | ✅ done | L78, `removeImageToGroups` L976 |
| Persistent `GroupValueIndex` (stable ids in-session) | ✅ done | not reset in `group()`, L341 keeps it |
| Epoch-ms date bucketing (no `Date` in scan) | ✅ done | `dateBucketKey` L146 |
| Pre-bucket before key construction (no per-slot spread) | ✅ done | `computePropertySubGroup` L909-962 |
| Direct buffer reads via `getRawBuffer` (skip `readSlot` dispatch) | ✅ done | group L891, sort L137, filter L236 |
| `computeImageOrder` / `imageIteratorOrder` deleted | ✅ done | `getImageOrder` now = `group.start + idx` L1335 |
| Filter as `Uint8Array` mask (no valid/reject arrays mid-pipeline) | ✅ done | `applyGroupFilterMask` L276 |
| Native packed-key sort (no JS comparator) | ✅ done | `sortByPackedKey` L195 |
| Float64 fast paths for numeric filter/sort | ✅ done | filter L234-251, sort L137-143 |

So the headline allocations from the 2024-era notes (`Instance[]` per node, 3M Date objects,
per-slot key spreads) are **gone**. What remains is finer-grained.

---

## 2. The group-id question: value→id mapping, reproducibility, and hashing

### 2.1 What the code does today

`GroupValueIndex` (`GroupManager.ts:242-271`) is a **trie of nested `Map`s** keyed by the
value path, with a monotonic `idCounter`:

```
get([v1, v2]):  walk index[v1][v2][null]; if absent assign idCounter++
```

- Called **once per unique group**, from the bucket loop (`computePropertySubGroup` L949) —
  *not* per slot. At 1M images / ~10k groups that is ~10k trie walks of ≤depth Map ops.
  Cost is **negligible** against the O(n) bucketing scan.
- The index is **persistent** — `group()` does not reset it (only `clear()` does, L587). So
  across rebuilds, the same value path keeps the same integer id regardless of
  insertion/sort order. View state (open/closed) transfer by id (L384-387) is therefore
  correct **within a session**.

### 2.2 So what is "reproducible group ids" actually asking for?

There are two different guarantees, and only one is missing:

| Guarantee | Have it? | Mechanism |
|---|---|---|
| Same logical group → same id across **rebuilds in one session** | ✅ yes | persistent trie |
| Same logical group → same id across **reloads / sessions / machines** | ❌ no | counter restarts at 1 on `clear()` (L587) |

Cross-session stability only matters if a group id is **persisted or sent externally** —
e.g. saving which groups are open/closed, deep-linking to a group, or a backend/plugin that
references a group by id. Today nothing persists group ids (`GroupState.options` is keyed by
**propertyId**, not group id, despite the type annotation — see `setGroupOption` L750), so the
gap is currently harmless. The question is whether to close it.

### 2.3 Would hashing destroy performance? No — but it solves the wrong problem

**Performance:** A hash of the value path computed **once per unique group** is sub-millisecond
over thousands of groups. The fear is only justified if you hash **per slot** (1M string
allocations) — but the architecture already buckets on the raw primitive value first
(`buckets = new Map<any, number[]>()`, L909) and assigns ids per bucket. As long as id
derivation stays in the per-bucket loop, **any** scheme (trie walk, hash, string key) is free
relative to the scan. So:

> Hashing will not kill performance. The bottleneck in `group()` is the O(n) bucketing pass,
> not the O(#groups) id assignment.

**Correctness:** hashing introduces a problem the trie does not have — **collisions**. With a
32-bit hash and k groups the birthday probability is ≈ k²/2³³:

| #groups | 32-bit collision prob | 53-bit collision prob |
|---|---|---|
| 1,000 | ~0.01% | ~1e-10 |
| 10,000 | ~1.2% | ~1e-8 |
| 50,000 | ~29% | ~1.4e-7 |

A collision silently merges two unrelated groups — unacceptable. To be correct you must use a
≥53-bit hash **and** still store the path to verify on hit (so you're storing the path
anyway). That is strictly more work than the trie for the in-memory id.

### 2.4 The "intern every value to an id" variant

Mapping each distinct property value to a small integer (`Map<value, valueId>` per property)
and composing the path of value-ids into one group id runs into:

- **Packing** the value-ids into a single integer (`v0 * scale0 + v1`) overflows
  `MAX_SAFE_INTEGER` for high-cardinality levels — the same overflow `sortByPackedKey`
  already has to guard against (`SortManager.ts:220`). Not robust.
- **Nesting** value-ids in a Map-of-Maps is exactly the current trie with an extra
  interning indirection — no benefit.

So interning-then-compose offers nothing over the trie.

### 2.5 Recommendation

1. **Keep the trie for the in-memory id.** It is already per-group-cheap, collision-free, and
   stable within a session. Do not hash for runtime ids.
2. **If/when cross-session stability is needed** (persisted open/closed, saved views,
   deep-links): persist the **canonical value path** — an array like
   `[[propId, value], …]` (date buckets already reduce to integers; tags to tag-ids;
   strings/numbers as-is) — and rebuild the id↔path mapping on load. The path is inherently
   reproducible and has **zero collision risk**. The integer id stays a private in-memory
   handle. This costs work only at save/restore time, never in the hot path.
3. **Protect one invariant:** trie keys must stay **primitives** (number/string/boolean).
   They are today (dates are integer bucket keys, tags are ids). If an object (e.g. a raw
   `Date`) ever became a key, `Map` reference-identity would break reproducibility. Worth a
   comment on `GroupValueIndex`.

Bottom line: the reproducibility you can cheaply get, you already have. The reproducibility
you don't have is best obtained by persisting the path, not by hashing.

---

## 3. GroupManager — remaining paths

### 3.1 `updateSelection` is secretly O(n) (highest-value group fix) ⚠️

The incremental path is supposed to touch only dirty instances, but `addUpdatedToGroups`
(called from `updateSelection` L710) contains two full-dataset passes:

- **`GroupManager.ts:444-448`** — re-sorts **every** non-cluster group's `slots` array on
  every incremental edit, ignoring `group.dirty`. This is redundant: `updateSelection`
  L719-729 already re-sorts the dirty Property groups afterward. The unconditional sweep is a
  superset doing O(Σ leaf·log leaf) ≈ O(n log) work for a K-instance edit.
- **`GroupManager.ts:450-454`** — `this.result.imageToGroups = new Map()` then re-adds every
  leaf group's every slot. This rebuilds the **entire** reverse index (O(n)) for a K-instance
  change, defeating the whole point of the Map+Set design.

**Fix:** in the incremental path, (a) drop the unconditional sort at L444-448 and rely on the
dirty-only sort at L719-729; (b) patch `imageToGroups` only for the changed instances —
remove the dirty ids' old leaf memberships (already known via `oldGroupIds` L678-682) and add
the new ones, instead of `new Map()`. Result: `updateSelection` becomes O(K·depth + #groups)
as intended. This is the single biggest grouping win after the iterator work.

### 3.2 Per-slot `Set` allocation in tag grouping

`computePropertySubGroup` L926-933 allocates a `new Set<number>()` per slot to dedupe the
expanded parent tags before bucketing. At 1M tag-grouped images that is 1M short-lived Sets.

**Fix:** replace with a generation-stamped scratch array — `seen: Int32Array(maxTagId+1)`,
stamped with a per-slot counter; a tag is "new for this slot" iff `seen[tag] !== gen`. Zero
allocation, same dedupe. Same pattern applies to `addInstanceToGroups` L491-498.

### 3.3 `addInstanceToGroups` rebuilds `tagWithParents` per slot

L471-477 builds the `tag → {parents}` map **inside** the per-slot loop, whereas
`computePropertySubGroup` correctly hoists it (L896-902). On the incremental path this is
O(K × #tags). **Fix:** hoist it out, or better, unify the two code paths (they implement the
same bucketing with different efficiency — long-standing duplication noted as Q10 in
[[group_manager_redesign_plan]]).

### 3.4 `Array.from(slots)` for the root

`group()` L342 does `buildRoot(Array.from(slots))` — converts the 1M `Int32Array` into a
regular `number[]` (V8 dictionary-mode risk + double the memory) just so leaf `.push()` works
elsewhere. **Fix:** keep root slots as the `Int32Array` (root is never `.push()`ed
incrementally — only leaves are), or store an explicit length. Minor memory/GC.

### 3.5 `buildOrdinalRanges` is O(n) on every update

L398-423 reallocates `orderedIds = new Int32Array(n)` and refills it on every `group()` **and**
every `updateSelection`. For incremental edits this is O(n) for a K-instance change. The notes'
"lazy `orderedIds` cache, patch affected leaves" (Q1/§8a in [[group_tree_structure_redesign]])
is the real fix; lower priority than 3.1 because it's a single linear typed-array fill (fast),
not a Map rebuild.

### 3.6 Tag reads via CSR instead of `sparse`

For tag grouping the scan reads `rawBuf?.[s]` = `col.sparse[slot]` — a pointer to a per-slot JS
array of boxed numbers (heap chase + boxing). The ColumnStore already builds a **CSR**
(`columnStore.ts:66-80`, refreshed L332/L464) that is two flat `Int32Array`s, but **no manager
reads it**. Reading a slot's tags from `csr.values[csr.offsets[slot] .. offsets[slot+1]]`
avoids the per-slot object and the boxing. Applies to grouping (§3.2) and tag filtering (§4.3).

---

## 4. FilterManager — remaining paths

### 4.1 Date filter allocates a `Date` per slot for nothing ⚠️

Dates are stored as epoch-ms in a `Float64Array` (`propertyKind(date) = 'numeric'`,
`columnStore.ts:17-25`), so `readSlot` returns a **number**. Yet the date branch
(`FilterManager.ts:220-230`) does `+new Date(raw)` per slot — a number→Date→number round-trip
allocating a `Date` each iteration, ~1M allocations per date filter.

**Fix:** delete the special date branch and let dates flow through the existing Float64
fast-path (L234-251) — they already satisfy `type !== string` and `buf instanceof Float64Array`,
and `>= <= < > == !=` are plain numeric compares. Convert the filter *value* once
(`+new Date(filter.value)`), as now. The `isSet`/`notSet` NaN checks there are already correct
for the NaN null-sentinel.

### 4.2 String filtering lowercases per slot

L253-261 (and text search L343, regex L370) call `raw.toLowerCase()` per slot — ~1M string
allocations per string filter/search. Unavoidable with raw columns. **Fix (medium):**
maintain a parallel pre-lowercased string column built once at load (and on write), as flagged
in [[managers_1m_optimization]] §4. Doubles string-column memory; removes the per-scan
allocation. Worth it only if string filtering/search is a measured hot spot.

### 4.3 Tag containment is O(n × tags); the inverted index exists but is unused ⚠️

`containsAny`/`containsAll`/`containsNot` (operatorMap L151-174) scan every active slot and do
nested `Set.has` loops. The ColumnStore already exposes `requireTagInverted(propId)` →
`tagInverted[tagId]: Int32Array` of sorted slots (`columnStore.ts:343-362`), **but FilterManager
never calls it.**

**Fix (high impact for selective tag filters):**
- `containsAny([t1,t2])` → sorted **union** of `tagInverted[t1] ∪ tagInverted[t2]`, set those
  mask bits. O(result) instead of O(n × tags).
- `containsAll([t1,t2])` → sorted **intersection**, O(min list).
- `containsNot` → still O(n) (complement) but no inner tag loop.
- Needs small `sortedMerge` / `sortedIntersect` helpers; fall back to the current CSR/sparse
  scan when the inverted index isn't loaded yet. Requires `_ensureColumns` to call
  `requireTagInverted` for tag filters.

### 4.4 OR-group allocations and the `hasTodo` rescan

`applyGroupFilterMask` OR branch (L294-313): allocates a fresh `workMask = new Uint8Array(n)`
per child and an O(n) `hasTodo` scan per child (L300-301). Bounded by #filters (usually small),
so low priority. **Fix if needed:** reuse one scratch `workMask` cleared per child; maintain a
live `todoCount` instead of rescanning.

### 4.5 `filterByPluginMask` indexes `instanceIds` as a function

L394/L403: `col.instanceIds[slots[i]]` — but `instanceIds` is a store **getter that returns the
array** (`columnStore.ts:519`), so `col.instanceIds[i]` indexes the *function object*, not the
array → `undefined`. Looks like a latent bug (works only if a Pinia unwrap masks it). Verify;
should be `col.instanceIds()[slots[i]]` like everywhere else (e.g. `updateSelection` L546 uses
`col.instanceIds[s]` too — same suspicious pattern). **Action: confirm whether `instanceIds` is
exposed as array or getter and make these consistent.**

---

## 5. SortManager — remaining paths

### 5.1 Delete `result.order` — dead 1M-key object ⚠️ (verified)

`SortManager.ts:382-383` and `445-446` build `result.order = { [slot]: position }` — a plain
object with up to 1M keys (V8 dictionary mode, full rehash) — on **every** `sort()` and **every**
`updateSelection()`. A full-tree grep (`src/**` ts+vue) finds **no reader**: GroupManager builds
its own `_posArr` from the slot order (`group()` L333-339) and never consumes `SortResult.order`;
the only `.order` reads in the app are `group.order` and unrelated mapview point ordering.

**Fix:** remove the field and both fill loops. If a future consumer needs slot→position, expose
an `Int32Array` (typed, O(1), no dictionary-mode object), not a plain object. Free win, removes
an O(n) object build from the two hottest sort exits.

### 5.2 `sortByPackedKey` boxes values into `any[]`

L207-217: `const vals: any[] = new Array(n)` then `vals[i] = col[slots[i]]`. For a
`Float64Array` column this **boxes** each double into the heap-backed `any[]`, and the unique
extraction (`Array.from(new Set(vals))`) boxes again. **Fix:** for numeric columns keep `vals`
as a `Float64Array(n)` (gather), dedupe via a numeric sort + linear scan or a `Set<number>`
seeded from the typed array. Removes 1M boxed slots per numeric sort column.

### 5.3 `buildSortCols` over-allocates for sparse high-slot sets

L127-155 allocates `Float64Array(maxSlot+1)` / `Array(maxSlot+1)` per property. The arrays are
**slot-indexed** (deliberate, so the cache survives insert/remove — comment L75-78), so size is
`maxSlot+1`, not `n`. For a small filtered set with a high max slot index (e.g. 200 results
whose max slot is 999,999) this allocates ~1M-element arrays to hold 200 values. **Trade-off,
not a clear bug:** slot-indexing is what makes `updateSortCols` (L159) O(K). Note it; only act
if "filter to few → sort" is shown to thrash memory. A bounded alternative is a `Map<slot,key>`
for tiny result sets.

### 5.4 String-column sort: `unique.sort()` default order

L216: string uniques sort by UTF-16 code unit, after `sortParser` lowercasing (L57). Consistent
and fast; just be aware it is not locale-aware (é vs e ordering). Acceptable for ranking.

---

## 6. ColumnStore — shared enablers

These are not bugs but levers the managers under-use:

1. **CSR built, never read by managers** (§3.6, §4.3). Either wire it in for tag scans or stop
   building it (`buildCSR` at load L332 and per-commit L464-466 costs an O(n) pass + 2 Int32Arrays).
   Right now it is pure cost with no consumer.
2. **`requireTagInverted` exists, never called** (§4.3). The biggest single algorithmic upgrade
   available is to actually use it.
3. **`getRawBuffer` everywhere** — the numeric/tag managers already bypass `readSlot` dispatch;
   the remaining `readSlot`-per-slot sites are string filter (§4.2), date filter (§4.1, fixable),
   tag filter (§4.3, fixable via inverted/CSR), and text/regex search.
4. **Web-worker readiness:** all heavy columns are already transferable typed arrays
   (`Float64Array`/`Uint8Array`/`Int32Array`). The pipeline (filter mask → sorted `Int32Array` →
   group `orderedIds`) is worker-friendly today; only string columns and Vue reactivity stay on
   the main thread. This is the highest-ceiling change (kills main-thread jank entirely) and is
   far cheaper now than in the `Instance[]` era. See [[managers_1m_optimization]] §7.

---

## 7. Cross-cutting: the iterator/scroller hot path (largest remaining alloc)

Although `GroupManager` no longer allocates iterators in an O(n) path (order is now
`group.start + idx`), **TreeScroller still does**: `computeImageLines`/`computeImagePileLines`
(`TreeScroller.vue:205-262`) call `ImageIterator.nextImages()` per image, each constructing a
new `ImageIterator` (index lookup + `getSlots` + `getSha1Group` + `shouldSkipGroup`). At 1M
images / all-open this is ~2M short-lived objects per `computeLines`, on every result change.

This is Phase 2/3 of [[group_tree_structure_redesign]] and the subject of
[[tree_scroller_computelines_optimization]] (arithmetic packing + descriptor lines + integer
cursors). It is the **largest remaining allocation source** in the whole pipeline and is out of
scope of the three manager files but driven by them. The enabling data already exists
(`orderedIds`, `Group.start/end`), so it is mostly a TreeScroller + `ImageLine.vue`/`PileLine.vue`
refactor.

---

## 8. Prioritized backlog

| # | Change | Where | Effort | Impact | Risk |
|---|---|---|---|---|---|
| 1 | Delete dead `result.order` | Sort L382,445 | 15 min | Med (O(n) obj build ×2/refresh) | none (verified unread) |
| 2 | Date filter → Float64 fast path | Filter L220-230 | 30 min | Med (1M Date alloc/filter) | low |
| 3 | Truly-incremental `updateSelection` (no full `imageToGroups` rebuild, no all-group sort) | Group L444-454 | 1 day | **High** (O(n)→O(K) per edit) | med — test view/selection |
| 4 | Per-slot tag `Set` → generation scratch | Group L926-933, 491-498 | 2 hr | Med (1M Set/tag-group) | low |
| 5 | Hoist/unify `tagWithParents` in `addInstanceToGroups` | Group L471-477 | 1 hr | Low–Med (incremental) | low |
| 6 | Tag inverted index for containsAny/All | Filter L263-270 + new helpers | 2–3 days | **High** (selective tag filters) | med |
| 7 | `sortByPackedKey` typed `vals` (no boxing) | Sort L207-217 | 2 hr | Med (numeric sorts) | low |
| 8 | Integer cursors + descriptor lines | TreeScroller + cells | 1–2 wk | **Very High** (~2M allocs/recompute) | high (consumer rewrite) |
| 9 | Web worker for filter/sort/group | pipeline | 1–2 wk | High (no main-thread jank) | high |
| 10 | Pre-lowercased string column | ColumnStore + Filter | 2–3 days | Med (string filter/search) | med (memory) |
| 11 | CSR-backed tag reads (or drop CSR) | Group/Filter + Store | 1 day | Low–Med | low |
| 12 | Lazy/patched `orderedIds` cache | Group L398-423 | 2–3 days | Med (incremental) | med |
| 13 | Persist value-path for cross-session group ids (only if needed) | Group `GroupValueIndex` | 1 day | feature, not perf | low |

### Recommended sequence

1. **This week, free wins:** #1, #2, #4, #7 — isolated, no API change, individually < ½ day.
2. **The real incremental fix:** #3 (and #5) — makes data-edit updates O(K) instead of O(n).
   This is what makes 1M-scale live editing feel instant.
3. **Algorithmic:** #6 (tag inverted index) — the only change that beats O(n) for a common
   filter, and the infrastructure is already in the store.
4. **Structural ceiling:** #8 then #9 — the iterator/scroller rewrite and the worker move are
   the changes that decouple interaction latency from dataset size. Largest effort, largest UX
   payoff. Track under [[group_tree_structure_redesign]] / [[tree_scroller_computelines_optimization]].
5. **Group ids:** keep the trie. Only do #13 if a feature needs persisted/shared group identity,
   and then persist the **path**, not a hash (§2.5).

---

## 9. Answering the original questions directly

> **What optimization paths do we still have?**

Three free correctness/waste fixes (#1, #2, #4), one high-value incremental fix (#3), one
high-value algorithmic fix already half-built in the store (#6, tag inverted index), and two
structural ceilings (#8 iterator/descriptor rewrite, #9 web worker). Plus minor sort/filter
micro-opts (#5, #7, #10–12). See §8.

> **Would it make sense to map every value to an id for reproducible group ids? Would hashing
> destroy performance?**

- Group ids are assigned **per group, not per slot**, so **hashing would not destroy
  performance** — that fear only applies if you hash per-slot, which the architecture already
  avoids.
- But you don't need hashing: the current trie already gives reproducible ids **within a
  session**, collision-free, essentially for free.
- The only thing missing is **cross-session** reproducibility, and the correct, collision-free
  way to get it is to **persist the value path** (`[[propId, value], …]`) and rebuild the
  id↔path map on load — not to hash. Hashing would only add collision risk (needs ≥53-bit +
  path verification) for no benefit over persisting the path. See §2.
