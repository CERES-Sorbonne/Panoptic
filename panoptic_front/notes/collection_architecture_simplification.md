# Collection Architecture Simplification — State / Compute / Result Separation + Multiple Collections per Tab

Related: [[tabstore_manager_reactivity_refactor]], [[new_data_store_design]],
[[group_manager_redesign_plan]], [[managers_1m_optimization]],
[[tree_scroller_update_flow]], [[VUE3_CODE_STYLE_GUIDE]]

> **Status: PROPOSAL.** This note rethinks the runtime side of a tab
> (`tabStore` → `TabManager` → `CollectionManager` → `FilterManager` /
> `SortManager` / `GroupManager`) for two reasons:
> 1. The current split of responsibilities is hard to reason about (dual
>    trigger paths, manager classes that mix config + result + behaviour).
> 2. We now want **one filter/sort/group pipeline per view** (multiple
>    collections per tab), which **reverses locked decision Q10** in
>    [[tabstore_manager_reactivity_refactor]] ("one shared collection per tab").

---

## 1. What the system must deliver

| # | Mission | Implication |
|---|---|---|
| M1 | Give UI elements access to **tab data & state** | TabState is small, fixed-size config → keep it **fully reactive + autosaved**. |
| M2 | Give UI access to the **final grouped tree** to render the collection | The tree spans 1M+ instances → it must **not** be deep-reactive. UI reads it imperatively, driven by a coarse signal. |
| M3 | Be careful about **deep reactivity at 1M+** | A hard boundary between *reactive config* and *non-reactive computed data*. Vue must never proxy a per-slot/per-group structure. |
| M4 | **Multiple collections per tab** — one filter/sort/group per view | Promote the pipeline config from tab-level to **per-view**; run one compute engine per view. |
| M5 | **Simplify** the filter↔sort↔group↔collection coordination | Collapse 4 coordinating classes into 1 engine + pure compute kernels; one trigger path, not two. |

The single organising principle that satisfies M1–M3 is a **reactivity
boundary**:

```
   REACTIVE (small, persisted)          NON-REACTIVE (large, derived)
   ┌──────────────────────┐  watch    ┌───────────────────────────┐  signal   ┌──────┐
   │ TabState              │ ───────►  │ Collection compute        │ ───────►  │  UI  │
   │  views[i].{filter,    │           │  filter→sort→group        │  version  │      │
   │   sort,group,display} │           │  → Result {tree,          │  bump     │ reads│
   │  visibleProps, …      │ ◄──────── │     orderedIds, …}        │           │ tree │
   └──────────────────────┘  autosave └───────────────────────────┘           └──────┘
```

Data flows **one way**: config → compute → result → UI. The only thing that
crosses *back* is autosave (config → backend) and user mutations (UI → config).

---

## 2. Current architecture & why it is hard to simplify

A tab today is `TabManager { state, collection: CollectionManager }`, and
`CollectionManager` owns `FilterManager`, `SortManager`, `GroupManager`. Each
sub-manager is a class that bundles **four unrelated things**:

1. a reference to a reactive **config slice** (`this.state`),
2. a non-reactive **result** (`this.result` — slot arrays / group tree),
3. **compute kernels** (`filter()` / `sort()` / `group()` + incremental variants),
4. **mutators** (`addNewFilter`, `setSort`, `setGroupOption`, …) + **two
   EventEmitters** (`onStateChange`, `onResultChange`).

### Pain points (what makes it hard to follow)

- **P-A — Two trigger paths that overlap.** Recompute is driven *both* by
  `CollectionManager`'s deep watches → `requestReload(kind)` (the real path
  today) *and* by the vestigial `onResultChange` cascade
  (`onFilter→sort→group`, `onSort→group`, wired at `CollectionManager.ts:68-70`).
  `update()` also chains filter→sort→group **inline** (`:182-186`). So the same
  ordering is expressed three times. The EventEmitter cascade is now mostly dead
  weight and a double-compute risk.
- **P-B — Mutators no longer trigger, but still live on managers.** Since B2
  ([[tabstore_manager_reactivity_refactor]]) moved triggering to watches, the
  manager mutators only do *bookkeeping* (filter-id minting + `filterIndex`,
  `_sortCols = null`, sha1 guards). Yet they still carry `onStateChange.emit()`
  calls that nothing meaningful consumes anymore.
- **P-C — Config + result + behaviour in one object.** You cannot look at a
  manager and tell which fields are persisted, which are reactive, which are
  hot 1M-row buffers. `GroupManager` even re-wraps its state in `reactive()`
  (`:297`), muddying the "single proxy" invariant from Pillar A.
- **P-D — Result reactivity is ad-hoc.** `runState` is reactive; the group tree
  is plain; selection is a `shallowRef`; folds live on plain tree nodes. UI
  components reach into `tab.collection.groupManager.result.*` and rely on a mix
  of `triggerRef`, `onResultChange` listeners, and manual `computeLines`
  recomputation. No single contract for "the result changed, re-render."
- **P-E — One collection per tab is baked in.** `TabManager` constructs exactly
  one `CollectionManager` from tab-level `filterState/sortState/groupState`.
  Two views share it (Q10). M4 needs the opposite.

The 1M-row **compute kernels themselves are good** (packed-key sort, bucketed
group, mask filter, incremental `updateSelection`) and stay — see
[[managers_1m_optimization]]. This note only changes **ownership, wiring, and
the reactivity boundary**, not the algorithms.

---

## 3. Proposed layering

Three layers, each with a single responsibility.

### Layer 1 — State (reactive, persisted, behaviour-free)

`TabState` and its slices are **plain reactive data**. No classes, no
EventEmitters, no compute. This is the only thing Vue proxies and the only
thing autosaved. Mutations are **pure helper functions** over the state object,
not methods that also recompute:

```ts
// state/filterOps.ts — pure, operate on a FilterState, no side effects beyond mutation
addFilter(filterState, propertyId, parentId?)   // mints a stable node id, pushes
updateFilter(filterState, nodeId, patch)
removeFilter(filterState, nodeId)
// likewise sortOps, groupOps
```

The **filter-id / `filterIndex` problem** (the one thing that made mutators
non-trivial) is solved by giving filter nodes **stable ids at creation** inside
these helpers, and looking a node up by walking the tree (it is tiny — a few
dozen nodes) instead of maintaining a parallel mutable `filterIndex` that has to
be kept in sync. No runtime index to invalidate → mutators become trivial and
the `recursiveRegister` / `nextIndex` machinery disappears.

### Layer 2 — Compute (the `Collection`, non-reactive)

One `Collection` runtime object **per view**. It is *not* reactive and is *not*
persisted. It:

- holds a reference to its config slice (`view.filterState` etc.),
- reads columns from `columnStore`,
- runs the pipeline and owns the incremental-update caches,
- exposes the `Result` + a coarse change signal.

The three managers collapse from coordinating classes into **stateless compute
kernels** (pure modules) plus the incremental caches that move onto the
`Collection`/`Result`:

```ts
// core/kernels/filter.ts, sort.ts, group.ts — pure functions
runFilter(state: FilterState, ctx, slots: Int32Array): { valid, reject }
runSort  (state: SortState,   ctx, slots: Int32Array, cache: SortCache): Int32Array
runGroup (state: GroupState,  ctx, slots: Int32Array, prev: GroupTree?): GroupTree
// + incremental variants: filterDelta / sortDelta / groupDelta(dirtyIds)
```

`Collection` is the only orchestrator (replacing `CollectionManager` + the
three manager classes' wiring):

```ts
class Collection {
    readonly config: ViewCollectionConfig      // ref into TabState (reactive)
    result: Result                              // plain, non-reactive
    signal: Reactive<{ version: number; status: 'idle'|'computing'; dirty: boolean }>
    private cache: { sort: SortCache; group: GroupTree | null }
    private runToken = 0
    private active = false

    // single entry — coalesced, debounced, active+autoReload gated, latest-wins token
    requestReload(kind: 'filter'|'sort'|'group'|'sortGroups'): void

    // incremental on data change (columnStore.onChange)
    applyDataChange(dirtyIds: Set<number>): void

    activate(): void   // recompute if dirty
    deactivate(): void // dirty-only
}
```

`requestReload` keeps the **good parts** of today's `CollectionManager`:
coalescing via `maxReloadKind`, debounce, `active`/`autoReload` gate,
monotonic `runToken`. It drops the EventEmitter cascade entirely — ordering is
the inline `filter→sort→group` it already does in `update()`.

### Layer 3 — Result (non-reactive data + one reactive signal)

```ts
interface Result {
    orderedIds: Int32Array          // DFS display order (M2)
    tree: GroupTree                 // plain objects, NEVER reactive
    // incremental caches live here, not in separate managers:
    filterSlots: Int32Array
    sortSlots: Int32Array
}
```

The **only** reactive thing the result exposes is
`signal.version` (a counter) + `status`. UI does:

```ts
watch(() => collection.signal.version, () => rebuildVisibleLines())  // imperative read of result.tree
```

This is exactly the [[tree_scroller_update_flow]] / `computeLines` pattern,
made the universal contract. No component ever deep-watches the tree; the 1M
structure stays out of Vue. `triggerRef(selectedImages)` and the per-manager
`onResultChange` emitters are replaced by `bumpVersion()`.

**Net simplification:** `CollectionManager` + `FilterManager` + `SortManager` +
`GroupManager` (4 stateful classes, 6 EventEmitters, 2 trigger paths) →
`Collection` (1 class, 1 signal, 1 trigger path) + 3 pure kernel modules +
small state-op helpers. The iterator classes (`GroupIterator`/`ImageIterator`)
stay as-is (they read the plain tree).

---

## 4. State model — multiple collections per tab (M4)

Today `filterState/sortState/groupState/collectionState` are **tab-level** and
`views[i]` holds only display. To get one pipeline per view, **fold the
collection config into the view**:

```ts
interface ViewState {
    // display (unchanged)
    type: ViewType
    imageSize: number
    mapOptions: MapOptions
    // collection config — NEW: was tab-level, now per-view
    collectionState: CollectionState
    filterState:     FilterState
    sortState:       SortState
    groupState:      GroupState
}

interface TabState {
    version, id, name
    splitView: boolean
    splitRatio: number
    views: ViewState[]              // 1..2 (keep the fixed pair if simpler)

    // SHARED across views (tab-level) — unchanged:
    visibleProperties, propertyOptions, selectedFolders, visibleFolders
    isSelection?: boolean
}
```

`TabManager` then owns **one `Collection` per view** instead of one shared
`CollectionManager`:

```ts
class TabManager {
    state: TabState
    collections: Collection[]       // collections[i] drives views[i]
    selection: TabSelection         // SHARED across views (see §5)
}
```

This is the clean inversion of Q10. Each view's scroller binds
`tab.collections[viewIndex]` instead of the shared `tab.collection`.

### What stays shared vs per-view

| State | Scope | Rationale |
|---|---|---|
| filter / sort / group / collectionState | **per-view** (M4) | the whole point |
| group folds (open/closed), result tree | **per-view** | a fold belongs to a specific tree |
| display (type, imageSize, mapOptions) | **per-view** | unchanged from Pillar F |
| selection (set of instance ids) | **shared (tab)** | selecting an image should reflect in both panes; selection is by id, collection-independent (§5) |
| visibleProperties, propertyOptions, selectedFolders | **shared (tab)** | columns/folders are a tab concept |

---

## 5. Selection — lift it out of the group tree

Today selection lives in `GroupManager` (`selectedImages: Ref`, `selectImages`,
`propagateSelect`, shift-select via iterators). With N collections per tab that
can't sit inside one group manager. Lift it to a **tab-level `TabSelection`**:

```ts
class TabSelection {
    private set = new Set<number>()        // instance ids, NON-reactive
    signal = reactive({ version: 0 })       // coarse reactive tick
    select(ids), deselect(ids), toggle(ids), clear()
    has(id): boolean                        // read in render, gated by signal.version
}
```

- Selection is **by instance id**, so it is naturally collection-independent and
  shared across views.
- Each `Collection` derives per-group `selected` flags from `TabSelection` when
  it (re)builds visible lines — it does **not** store selection in the tree.
- Shift-select still uses the view's own `GroupIterator` (range within *that*
  view's order), then calls `tabSelection.select(ids)`.
- `collectionState.filterBySelection` reads `tabSelection` — works unchanged.

This removes `selectedImages`, `triggerRef`, and ~150 lines of selection code
from `GroupManager`, leaving it (now the `group` kernel) purely structural.

---

## 6. Orchestration & lifecycle

### One trigger path

Replace **all** of: the `onStateChange`/`onResultChange` EventEmitters, the
`onFilter/onSort/onGroup` cascade, and the scattered manual `update(true)`
calls — with **one watch per collection config** mapped to `requestReload`:

```ts
// inside Collection, on its own config slice
watch(() => config.filterState, () => requestReload('filter'),     { deep: true })
watch(() => config.sortState,   () => requestReload('sort'),       { deep: true })
watch(() => config.groupState.groupBy, () => requestReload('group'))
watch(() => config.groupState.options, () => requestReload('sortGroups'), { deep: true })
// sha1Mode stays an inline restructure (not watched), as today
```

(These are small config objects — deep-watching them is cheap; the 1M data is in
the non-reactive Result, which Vue never sees. Same justification as Q5.)

### Active-gating with multiple live collections

Today only the single active tab's single collection recomputes. Now:

- **Background tab** → all its collections `deactivate()` (dirty-only).
- **Active tab, no split** → only `collections[0]` active; `collections[1]`
  stays dirty and `activate()`s lazily when the user enables split.
- **Active tab, split on** → both active.

So `selectMainTab` / split-toggle drive `activate()`/`deactivate()` per
collection. `columnStore.onChange` (data edits) fans out to every **active**
collection's `applyDataChange`.

### Autosave (unchanged in spirit)

Still one debounced deep watch on the active `TabState` (Pillar C). Because the
per-view collection config now lives *in* `TabState`, it is covered
automatically. The Result and `TabSelection` are non-reactive and outside
`TabState`, so they are never serialized — the existing "never stuff transient
fields into TabState" rule still gives a correct payload for free.

---

## 7. What each current file becomes

| Today | Becomes |
|---|---|
| `CollectionManager` | `Collection` (the only orchestrator; keeps `requestReload` coalescing/debounce/token) |
| `FilterManager` | `core/kernels/filter.ts` (pure `runFilter`/`filterDelta`) + `state/filterOps.ts` (mutators) |
| `SortManager` | `core/kernels/sort.ts` (`runSort`/`sortDelta`, `SortCache` moves to `Collection`) |
| `GroupManager` | `core/kernels/group.ts` (tree build + delta) ; **selection split out** to `TabSelection` ; iterators kept |
| `TabManager` | owns `collections: Collection[]` + `TabSelection`; thins out |
| `tabStore` | unchanged in shape; `importTab` still wraps once + shares proxy (Pillar A) |
| per-manager `onStateChange`/`onResultChange` | deleted → `signal.version` |

---

## 8. Suggested sequencing

1. **Result signal first.** Introduce `signal.version` on the existing
   `CollectionManager` and migrate scrollers to `watch(version)` +
   imperative tree reads, retiring `onResultChange`. *Low risk, isolates M2/M3.*
2. **Lift selection** to `TabSelection`; repoint `GroupManager` selection calls.
   *Independent; shrinks GroupManager.*
3. **Collapse the trigger path** — delete the EventEmitter cascade and dead
   `onStateChange` emits; keep only the config watches → `requestReload`.
4. **Extract kernels** — turn `filter()/sort()/group()` into pure functions;
   move caches onto a `Result`/`Collection`. Mutators → state-op helpers; drop
   `filterIndex`/`nextIndex` in favour of stable creation-time ids.
5. **Per-view collections (M4)** — move `filter/sort/group/collectionState`
   into `ViewState`; `TabManager.collections[]`; per-collection activate/split
   gating. **Bumps `TAB_MODEL_VERSION`** → warn + reset (Q9), no migrator.

Steps 1–4 are refactors with no behaviour change and are independently
shippable. Step 5 is the feature (multiple collections) and the only one that
changes the persisted model.

---

## 9. Open questions

- **Q-A — How many collections?** Fixed pair mirroring `views`, or a free list a
  view points at by index (would allow a third "detail" pipeline later)? Default:
  one collection per view, fixed pair, simplest.
- **Q-B — Column lifetime.** Two views can require disjoint columns. `columnStore`
  full-column fetch is shared/cached, so this is additive — but confirm no eviction
  drops a column the *other* collection still needs.
- **Q-C — Folds & selection on split.** Folds per-view (decided §4); selection
  shared (decided §5). Confirm shift-select range semantics when the two panes
  have *different* group structures (range is within the acting view only —
  proposed).
- **Q-D — Recompute cost of two live pipelines.** Split on a 1M collection now
  runs two filter→sort→group passes. Acceptable because each view is usually a
  *different* (often narrower) collection; but the debounce/active gate must keep
  a background-but-split-visible pane from thrashing on shared data edits.
- **Q-E — Does the `Collection` need to be a class at all?** Could be a factory
  returning `{ result, signal, requestReload, … }` closures (matches the store
  style in [[VUE3_CODE_STYLE_GUIDE]]). Class chosen here only for readability of
  the proposal.
