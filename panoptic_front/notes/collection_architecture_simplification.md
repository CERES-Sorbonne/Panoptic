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
thing autosaved.

**Most mutations are just direct assignments** on the reactive state
(`tab.name = …`, `tab.visibleProperties[id] = true`, `view.type = 'grid'`) — no
method, no helper (see §8). Only the handful with genuine structural bookkeeping
get a **pure helper**: building a filter node (stable id at creation), adding or
removing a sort/group key. These helpers have no side effect beyond mutating the
state — they never recompute (the watch in §6 does):

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

`Collection` is the only orchestrator (replacing `CollectionManager` + the three
manager classes' wiring). It is a **factory** (Q-E), not a class:

```ts
// core/collection.ts — createCollection(config) → Collection
function createCollection(config: CollectionConfig) {
    const result: Result = emptyResult()         // plain, non-reactive

    // Q-I: version / status / dirty are SEPARATE refs, so watching `version`
    // (high-frequency, fires on every recompute) never wakes spinner / reload-button
    // watchers bound to status/dirty.
    const version = ref(0)                        // bump after each result change → UI re-reads tree
    const status  = ref<'idle' | 'computing'>('idle')
    const dirty   = ref(false)

    let cache = { sort: null as SortCache | null, group: null as GroupTree | null }
    let runToken = 0
    let active = false

    function requestReload(kind: 'filter'|'sort'|'group'|'sortGroups'): void { /* … */ }
    function applyDataChange(dirtyIds: Set<number>): void { /* columnStore.onChange */ }
    function activate(): void   { /* recompute if dirty */ }
    function deactivate(): void { /* dirty-only */ }
    function dispose(): void    { /* stop the config watches (Q-F) */ }

    return { config, result, version, status, dirty,
             requestReload, applyDataChange, activate, deactivate, dispose }
}
export type Collection = ReturnType<typeof createCollection>
```

`requestReload` keeps the **good parts** of today's `CollectionManager`:
coalescing via `maxReloadKind`, debounce, `active`/`autoReload` gate,
monotonic `runToken`. It drops the EventEmitter cascade entirely — ordering is
the inline `filter→sort→group` it already does in `update()`.

### Layer 3 — Result (non-reactive data + a reactive version tick)

```ts
interface Result {
    orderedIds: Int32Array          // DFS display order (M2)
    tree: GroupTree                 // plain objects, NEVER reactive
    // incremental caches live here, not in separate managers:
    filterSlots: Int32Array
    sortSlots: Int32Array
}
```

The **only** reactive thing the result exposes is the `version` ref (Q-I). UI does:

```ts
watch(() => collection.version, () => rebuildVisibleLines())  // imperative read of result.tree
```

This is exactly the [[tree_scroller_update_flow]] / `computeLines` pattern,
made the universal contract. No component ever deep-watches the tree; the 1M
structure stays out of Vue. The per-manager `onResultChange` emitters collapse
into this one `version` bump. (Selection changes have their *own* equivalent
signal on `columnStore` — §5 — so `triggerRef(selectedImages)` goes away
entirely.)

**Net simplification:** `CollectionManager` + `FilterManager` + `SortManager` +
`GroupManager` (4 stateful classes, 6 EventEmitters, 2 trigger paths) →
`Collection` (1 factory, 1 version tick, 1 trigger path) + 3 pure kernel modules +
small state-op helpers. The iterator classes (`GroupIterator`/`ImageIterator`)
stay as-is (they read the plain tree).

---

## 4. State model — multiple collections per tab (M4)

Today `filterState/sortState/groupState/collectionState` are **tab-level** and
`views[i]` holds only display. To get one pipeline per view, **fold the
collection config into the view**:

Per **Q-A**, two views may **share one collection or each own theirs**, so the
collection config is *not* folded into the view — it is a tab-level list that
views **reference by id**:

```ts
interface CollectionConfig {            // the filter/sort/group pipeline config
    id: string
    collectionState: CollectionState
    filterState:     FilterState
    sortState:       SortState
    groupState:      GroupState
}

interface ViewState {                   // display only
    type: ViewType
    imageSize: number
    mapOptions: MapOptions
    collectionId: string                // which collection this view renders
}

interface TabState {
    version, id, name
    splitView: boolean
    splitRatio: number
    views: ViewState[]                  // 1..2
    collections: CollectionConfig[]     // 1..2 — both views may point at the SAME
                                        //   id (shared) or different ids (own)

    // SHARED across views (tab-level) — unchanged:
    visibleProperties, propertyOptions, selectedFolders, visibleFolders
    isSelection?: boolean
}
```

The runtime holds **one `Collection` per distinct, currently-visible
`collectionId`** (so a shared collection is computed once, not twice). *Where*
those instances live is §8 — the store owns `Map<collectionId, Collection>`,
created when a referencing view becomes visible and disposed when the last
referencing view closes (**Q-F**); `TabManager` goes away. Each view's scroller
binds the `Collection` for its `collectionId` instead of the shared
`tab.collection`. This is the clean inversion of Q10.

### What stays shared vs per-view

| State | Scope | Rationale |
|---|---|---|
| filter / sort / group / collectionState | **per-view** (M4) | the whole point |
| group folds (open/closed), result tree | **per-view** | a fold belongs to a specific tree |
| display (type, imageSize, mapOptions) | **per-view** | unchanged from Pillar F |
| instance selection (slot mask) | **global, non-persistent** | survives tab *and* view switches; reset on reload. Already lives in `columnStore.selectionMask` (§5) |
| visibleProperties, propertyOptions, selectedFolders | **shared (tab)** | columns/folders are a tab concept |

---

## 5. Selection is GLOBAL — and it already exists in `columnStore`

The intended behaviour: instance selection is **global** — it **survives tab and
view switches** — and is **not persisted** (resets on reload). So it is not a
property of a tab, a view, or a collection.

**We do not need to build anything for this.** `columnStore` already implements
exactly the optimized, slot-indexed selection this calls for — *"selected is just
a property"* taken literally as a bool mask parallel to `deletedMask`:

```ts
// columnStore.ts — ALREADY PRESENT
let selectionMask = new Uint8Array(0)        // slot-indexed; grows in init()/addInstances()
function isSelected(slot): boolean           // selectionMask[slot] === 1
function select(slots: number[])             // set bits + onSelectionChange.emit()
function deselect(slots: number[])
function clearSelection()
const onSelectionChange = new EventEmitter() // the change signal
```

This is already everything the spec wants:

- **Global** — `columnStore` is one app-wide singleton, so selection is shared by
  every tab and every view for free. No `TabSelection`, no copying.
- **Non-persistent** — a `Uint8Array` in memory, never in `TabState`, never
  serialized → empty after reload by construction.
- **Out of the reactivity boundary (M3)** — the mask is non-reactive and can hold
  1M slots; change is signaled via `onSelectionChange` (same imperative-signal
  contract as the Result, §3). Components subscribe and read `isSelected(slot)`,
  exactly as the `<InstanceData>` sketch in [[new_data_store_design]] does.
- **Slot-keyed, like the compute pipeline** — filter/sort/group already work in
  slots, and the iterators already carry slots, so selection ops need no
  id→slot mapping.

### The actual problem: there are two selection mechanisms — converge on the mask

Today **two** selections coexist and only the worse one is wired up:

| | keyed by | reactive? | used by |
|---|---|---|---|
| `GroupManager.selectedImages: Ref<{[id]:boolean}>` | instance id | yes (`triggerRef`) | **everything today** (`CollectionManager.ts:120,174`, `propagateSelect`, shift-select) |
| `columnStore.selectionMask: Uint8Array` | slot | no (emitter) | **nothing yet** — the intended design |

The fix is to **delete `selectedImages` and route all selection through the
`columnStore` mask**:

- `GroupManager.selectImages/unselectImages/clearSelection/select(Un)selectGroup`
  → thin wrappers over `columnStore.select(slots)` / `deselect(slots)` (drop the
  `ids[s]` round-trips and `triggerRef`).
- `group.view.selected` / `propagateSelect` read `columnStore.isSelected(slot)`
  over the group's slots.
- Shift-select uses the acting view's `GroupIterator` for the *range* (within that
  view's display order), then calls `columnStore.select(slots)`.
- `collectionState.filterBySelection` reads the mask directly — and since
  `select`/`deselect` mutate a slot array, "filter by selection" can scan
  `selectionMask` in the filter kernel **exactly like a bool column** (no special
  case), reacting to selections made in any tab.

This removes `selectedImages`, `triggerRef`, and ~150 lines of selection code
from `GroupManager`, leaving the `group` kernel purely structural — and selection
ends up owned by `columnStore`, hanging off **no** `TabManager`/`Collection`
(another nudge toward §8).

> Optional ergonomic add: a tiny reactive `selectionVersion` ref bumped inside
> `select/deselect/clearSelection` alongside the emitter, so templates can
> `watch(version)` instead of manual `onSelectionChange.on/off` in
> `onMounted/onUnmounted`. Keep the mask itself non-reactive.

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
collection — orchestrated by the **store** (§8). `columnStore.onChange` (data
edits) fans out to every **active** collection's `applyDataChange`.

### Autosave (unchanged in spirit)

Still one debounced deep watch on the active `TabState` (Pillar C). Because the
per-view collection config now lives *in* `TabState`, it is covered
automatically. The Result and the `columnStore` selection mask are non-reactive
and outside `TabState`, so they are never serialized — the existing "never stuff
transient fields into TabState" rule still gives a correct payload for free.

---

## 7. What each current file becomes

| Today | Becomes |
|---|---|
| `CollectionManager` | `Collection` (the only orchestrator; keeps `requestReload` coalescing/debounce/token) |
| `FilterManager` | `core/kernels/filter.ts` (pure `runFilter`/`filterDelta`) + `state/filterOps.ts` (mutators) |
| `SortManager` | `core/kernels/sort.ts` (`runSort`/`sortDelta`, `SortCache` moves to `Collection`) |
| `GroupManager` | `core/kernels/group.ts` (tree build + delta) ; **selection routed to `columnStore.selectionMask`** ; iterators kept |
| `TabManager` | **deleted** (§8); lifecycle role → `tabStore`; setters → direct reactive assignment on `TabState`; `verifyState` → pure `verifyTabState()` |
| `tabStore` | owns `tabs` (reactive) **+** `Map<tabId, Collection[]>` (non-reactive runtime); `importTab` still wraps once + shares proxy (Pillar A) |
| `GroupManager.selectedImages` | **deleted** — converge on existing `columnStore.selectionMask` (global, non-persistent) |
| per-manager `onStateChange`/`onResultChange` | deleted → `collection.version` ref |

---

## 8. Do we still need a `TabManager`?

**No — as a class it can go away.** Walking its current responsibilities:

| `TabManager` does today | Where it goes |
|---|---|
| holds `state` + the `CollectionManager` | `state` is just `tabStore.tabs[id]` (reactive); the collections move to a store-owned `Map` (below) |
| `activate()` / `deactivate()` | the **only irreducible job** — the store does it (below) |
| `verifyState()` reconciliation | pure `verifyTabState(state, dataStore)` — no class needed |
| `setVisibleProperty` / `setViewType` / `renameTab` / `setSelectedFolder` | **nothing** — direct reactive assignment (below) |
| `getVisibleProperties` (derived read) | a small `computed`/composable `visibleProperties(tab, data)` — *not* an assignment |
| `getSha1Mode` | reads `view.groupState.sha1Mode` — plain state read |
| selection helpers | gone — global `columnStore.selectionMask` (§5) |

**The setters are not "helpers" at all — they are one-line writes to a reactive
object.** None mints an id, invalidates a cache, or triggers recompute (these
fields are display/shared state, not filter/sort/group config). With Pillar A
(`TabState` reactive) and Pillar C (autosave = deep watch on `TabState`), a
component just assigns and both UI update and persistence follow for free:

```ts
tab.visibleProperties[propId] = true   // was setVisibleProperty(propId, true)
tab.views[viewIndex].type = 'grid'     // was setViewType(viewIndex, 'grid')
tab.name = newName                     // was renameTab(newName)
```

So there is **no `tabOps.ts`** for this category. The only mutations that keep a
helper are the ones with genuine bookkeeping — filter node creation (id minting),
sort/group add/remove — and those are the `filterOps/sortOps/groupOps` from §3,
which sit next to the config, not a tab-level layer. Everything else is a write.

Once selection is global (§5, already in `columnStore`) and config is plain
reactive `TabState`, the
*single* thing that genuinely needs a per-tab runtime owner is the set of
**non-reactive `Collection` instances** — they can't live inside the reactive
`TabState` (the boundary, M3), and there are now N of them per tab. That is not
enough to justify a class with a dozen helper methods. Put it in the store:

```ts
// tabStore — reactive config and non-reactive runtime side by side
const tabs = reactive<Record<string, TabState>>({})        // persisted, reactive
const collections = new Map<string, Collection>()          // collectionId → runtime (NON-reactive)

function importTab(raw: TabState) {
    const tab = reactive(raw)                               // Pillar A: one proxy
    tabs[tab.id] = tab
    verifyTabState(tab, useDataStore())
    // Collections are created lazily when a view becomes visible (Q-F) — not here.
}

// Create on demand for a collectionId a visible view references; reuse if it
// already exists (so two views sharing an id compute once — Q-A).
function ensureCollection(tab: TabState, collectionId: string): Collection {
    let c = collections.get(collectionId)
    if (!c) {
        const cfg = tab.collections.find(c => c.id === collectionId)
        c = createCollection(cfg)                           // factory (Q-E)
        collections.set(collectionId, c)
    }
    return c
}

// Reconcile live collections to the active tab's *visible* views (Q-F):
// create the ones now shown, dispose the ones no view references anymore.
function syncVisibleCollections() {
    const wanted = new Set(visibleViews(activeTab).map(v => v.collectionId))
    for (const [id, c] of collections) {
        if (wanted.has(id)) c.activate()
        else { c.dispose(); collections.delete(id) }        // last referencing view closed
    }
    for (const id of wanted) ensureCollection(activeTab, id).activate()
}
// called from selectMainTab and the split-toggle
```

UI access (M1) is then two small composables instead of one injected manager:

```ts
useCurrentTab(): ComputedRef<TabState>          // the reactive config
useCollection(viewIndex): Collection            // runtime for a pane (resolves view.collectionId)
```

**Cost — call-site churn.** Pillar D deliberately injected the whole
`TabManager` (Q4) to avoid touching the ~29 `tab.collection.groupManager` / ~21
`filterManager` / `tab.setVisibleProperty(...)` sites. Dropping the class
re-touches them. But **M4 already forces `tab.collection` → `collections[i]`
everywhere**, so those sites are being edited regardless — this is the moment to
also drop the class rather than preserve a now-hollow wrapper. The visible-
property / rename / viewType call sites become **direct assignments** on the
reactive `tab` (no wrapper call at all), which is mechanical.

> **If you want to keep one object** for injection convenience, keep a 15-line
> *struct* `{ state, collections }` with **no behaviour** (selection is global in
> `columnStore`, so it isn't even part of this) — but that is just the store entry
> by another name. The recommendation is: no `TabManager`.

---

## 9. Suggested sequencing

1. **Result signal first.** ✅ **DONE** (build green). Added `version: Ref<number>`
   to `GroupManager` (bumped via `emitResult()` wherever the tree changes) and
   migrated all 6 external consumers (`TreeScroller`, `GridScroller`, `TableHeader`,
   `GraphView`, `MapView`, `RecommendedMenu`) from `onResultChange` listeners to
   `watch(() => gm.version.value, …)`. `onResultChange` kept for now (internal
   `CollectionManager` cascade; removed in step 3). Separate `status`/`dirty` refs
   land with the `Collection` factory in step 4. *Low risk, isolated M2/M3.*
2. **Converge selection on `columnStore.selectionMask`** (§5). ✅ **DONE** (build
   green). Added a reactive `selectionVersion` ref + `isSelectedId`/`selectIds`/
   `deselectIds`/`getSelectedIds`/`selectedCount` to `columnStore`. Deleted
   `GroupManager.selectedImages` (+ `triggerRef`/`shallowRef`); its select/toggle/
   `propagateSelect` now read/write the slot mask. `CollectionManager.filterBySelection`
   reads `col.isSelected(slot)`. Migrated ~13 components: dropped the threaded
   `selectedImages` prop, each reads `col.isSelected(Id)` gated by
   `col.selectionVersion.value` (scrollers/lines, modals, map, ContentFilter).
3. **Collapse the trigger path** — ✅ **DONE** (build green). Removed the
   `CollectionManager` `onResultChange` cascade wiring (`onFilter`/`onSort`/
   `onGroup` listeners) and the three methods — `filter()`/`sort()` were only ever
   called `emit=false`, so the cascade was dead; ordering stays inline in
   `update()`/`runReload()`. Dropped now-unused `FilterResult`/`SortResult`
   imports. (`FilterManager`/`SortManager` keep their unused `onResultChange`/
   `onStateChange` emitters for now — removed when they become kernels in step 4.)
4. **Extract kernels** — ⏸ **DEFERRED (optional).** Turn `filter()/sort()/group()`
   into pure functions; move caches onto a `Result`/`Collection`; drop
   `filterIndex`/`nextIndex` for stable creation-time ids. *Pure internal
   restructuring of ~2000 lines of perf-critical, unverified code; high
   regression risk, no user-facing value, and NOT a prerequisite for step 5.
   Recommend doing it after step 5 ships and is runtime-verified, if at all.*
5. **Per-view collections (M4) + drop `TabManager` (§8)** — ⏳ **PENDING.** Move
   `filter/sort/group/collectionState` into a tab-level `collections[]` referenced
   by views (`collectionId`); store owns `Map<collectionId, Collection>`; replace
   the injected `TabManager` with `useCurrentTab()`/`useCollection(i)` (trivial
   setters become direct assignments); per-collection activate/split gating.
   **Bumps `TAB_MODEL_VERSION`** → warn + reset (Q9), no migrator. *Large
   (~22 files + builder/models migration) and changes the PERSISTED model (resets
   saved tabs). Can use the existing `CollectionManager` class as-is — does not
   need step 4. Do as a dedicated pass against a runtime-verified steps 1–3.*

Steps 1–3 are behaviour-preserving refactors, all build-green and independently
shippable. Step 4 is optional/deferred. Step 5 is the feature (multiple
collections) and the only one that changes the persisted model and retires
`TabManager`.

---

## 10. Open questions

### Settled while writing this note (recorded so they aren't re-litigated)

- **Reactivity boundary** → reactive `TabState` config; non-reactive `Collection`
  compute + `Result`; UI driven by a coarse `signal.version` / emitter (§1, §3).
- **Selection** → **global, non-persistent, slot-indexed**, already implemented as
  `columnStore.selectionMask`. Delete `GroupManager.selectedImages`; do **not**
  build a new selection store (§5).
- **`TabManager`** → **removed.** The store owns a non-reactive
  `Map<tabId, Collection[]>` and drives activate/deactivate; trivial setters
  become direct reactive assignments; `verifyState` → pure `verifyTabState()` (§8).
- **Per-view config** → `filter/sort/group/collectionState` move into `ViewState`;
  one `Collection` per view (§4). Reverses Q10.

### Resolved (David, 2026-06-08)

- **Q-A — How many collections? → 1 or 2 views at once; a view may share or own a
  collection.** So collection config is a tab-level `collections[]` list and views
  reference it by `collectionId` (§4); a shared id computes once.
- **Q-B — Column lifetime → no eviction.** Lazy column load only accelerates first
  load; memory is assumed sufficient. Nothing to drop.
- **Q-C — Shift-select → per view only.** Range computed within the acting view;
  no shift-select spanning the two panes.
- **Q-E — `Collection` → a factory** (`createCollection(config)`), not a class (§3).
- **Q-F — Lifecycle → created when its view becomes visible, disposed when the view
  closes** (`syncVisibleCollections`, §8). A shared collection lives while any
  referencing view is visible.
- **Q-G — Instance deletion → out of scope for now.** Don't special-case stale
  `selectionMask` bits on deleted slots yet.
- **Q-I — Signal shape → keep `version` separate from `status`/`dirty`** (separate
  refs), so a `watch(version)` never fires on a dirty/status change (§3 Layer 2/3).

### Still open

- **Q-D — Recompute cost of two live pipelines.** With split + two *own*
  collections, a shared-data edit fans out to both. Sharing (Q-A) collapses this to
  one when the views use the same collection; for the distinct-collection case the
  debounce/active gate must keep the second pane from thrashing. Revisit if split on
  1M feels heavy.
- **Q-H — `verifyTabState` dirtying autosave.** It runs on every activate and
  reassigns `propertyOptions`, triggering one debounced autosave per tab switch.
  Make it idempotent (write only when something actually changed) so a plain switch
  doesn't persist. *(Fold in during step 5.)*
