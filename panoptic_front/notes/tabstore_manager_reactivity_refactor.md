# TabStore / Manager Reactivity & Autosave — Refactor Plan & Open Questions

Related: [[panoptic_store_analysis]], [[new_data_store_design]], [[group_manager_redesign_plan]],
[[VUE3_CODE_STYLE_GUIDE]], [[frontend_settings_storage]]

This note proposes a rework of how a tab's state lives, mutates, reacts, and persists.
It covers the `tabStore`, `TabManager`, and the three managers (`FilterManager`,
`SortManager`, `GroupManager`) + `CollectionManager`.

---

## 0. Decisions locked

| # | Decision | Choice |
|---|---|---|
| Q1 | State ownership | **TabState is the container.** Managers hold references into its slices; invariant `manager.state === tabs[id].filterState`. Serialize the TabState directly. |
| Q2 | Recompute model | **Granular watchers (B2), orchestrated by the CollectionManager.** Keep `setX()` mutators; drop the manual `update(true)` calls. The CollectionManager watches each state slice (filter / sort / group / sortGroups) and is the single point that decides whether/what/when to recompute — generalising its existing `setDirty` role. Active-gated + autoReload-gated + debounced. |
| Q5 | Trigger mechanism | **Deep watch** per persisted slice. Acceptable here because the watched objects are *config* (filter tree, `groupBy`, per-prop options) — small; the 1M-row data lives in `result`/columnStore, never in these slices. The cost is the *recompute*, not the watch traversal. |
| Q8 | Current tab | **Singular main tab, always exactly one active.** "Split" is a property *of that tab*: the tab holds 1–2 **views** (see Pillar F). Never two tabs at once. |
| Q3 | Autosave scope | **Active tab only + flush-on-switch.** Watch only the main tab; flush pending save when switching away. |
| Q4 | Provider payload | **Full `TabManager`.** Provide/inject the manager; least churn for the 50+ `tab.collection.*` call sites. |
| Q6 | Persist view-state | **Persist nothing transient.** Folds + selection reset on reload → recompute can rebuild the group tree freely, no re-apply step. |
| Q9 | Version bump | **Warn + reset explicitly.** On `version` mismatch, log a warning and reset that tab to default (no silent drop, no migrators). |
| Q10 | Collection scope | **Shared.** One `CollectionManager` (filter/sort/group) per tab; both views display the same result. Shared selection + group folds across panes. |
| Q11 | Per-view fields | **Only `type` + `imageSize` + `mapOptions`.** Everything else (`visibleProperties`, `propertyOptions`, `selectedFolders`, …) stays tab-level/shared. |
| Q12 | View structure | **Fixed pair** `views: [ViewState, ViewState]`; `splitView` toggles view2 visibility. |
| Q13 | Split layout | **Move to tab.** `splitView` + `splitRatio` both live in `TabState` (per-tab geometry); migrate out of `uiStore`. |

Consequences to honour in §4:
- B2 is **multiple deep watches in the CollectionManager**, one per recompute entrypoint —
  *not* one deep watch over the whole state (that can't pick the right entrypoint). A change
  to `groupBy` also writes `options` (via `setGroupOption`), so two watches fire → the
  collection's single `requestReload` **coalesces** them, keeping the most expensive (`group`
  ⊃ `sortGroups`) and running the pipeline once, in order. One orchestrator, no per-manager
  scheduler.
- Singular main tab means the provider (Pillar D) keys on one `mainTab`; only the main
  tab's manager is active, so autosave/recompute effectively track that one manager.
- Q6 = persist nothing → **recompute is free to discard fold/selection**; B2 needs no
  preserve-and-reapply logic. Simplifies the scheduler.
- Q3 active-only accepts one gap: a *background* tab reconciled by `verifyState()` (e.g.
  after a property delete) won't re-persist until it is next activated. Acceptable —
  `verifyState()` re-runs on load anyway, so stale persisted state self-heals.

---

## 1. Current architecture (as built)

A tab exists as **three things at once**:

| Thing | Type | Reactive? | Holds |
|---|---|---|---|
| `tabStore.mainTab` | `ref<string>` | ✅ | active tab id |
| `tabStore.tabs[id]` | `reactive<Record<string, TabState>>` | ✅ (proxy on read) | serializable state |
| `managers[id]` | module-global `let managers = {}` | ❌ | `TabManager` (state **+ behaviour**) |

`TabManager` wraps a `TabState` and owns a `CollectionManager`, which wires
`FilterManager → SortManager → GroupManager`. Each sub-manager keeps `this.state`
pointing at a slice of the `TabState` (`filterState` / `sortState` / `groupState` /
`collectionState`).

**Mutation today is a manual two-step**, repeated in every form
(`GroupForm.vue:19-22`):

```ts
props.manager.setGroupOption(id)   // mutate state + onStateChange.emit()
props.manager.update(true)         // recompute slots + onResultChange.emit()
```

**Persistence today** is per-emit and synchronous:

```
manager.setX() → onStateChange.emit()
  → TabManager.saveManagerStates() → saveState()
  → tabStore.updateTabStateInStorage(id) → apiUpdateTabState(id, state)   // no debounce
```

---

## 2. Root problems (with evidence)

### P1 — Manager-state reactivity depends on how the tab was born. *(the core bug)*

- **New tab**: `buildTabState()` returns `reactive({... createFilterState(), ...})`
  (`builder.ts:9`), and each `create*State()` is itself `reactive(...)`. The TabManager
  receives the reactive proxy → `manager.state` is reactive.
- **Loaded tab**: `apiGetAllTabs()` returns **plain JSON**. `importTab()` does
  `tabs[id] = tab` (so `tabs[id]` *reads back* as a deep proxy) **but passes the raw
  `tab` to `new TabManager(tab)`** (`tabStore.ts:48-49`). The managers receive
  **raw, non-reactive** slices. `FilterManager`/`SortManager`/`GroupManager` store
  `this.state = state` without re-wrapping.

→ The same screen is reactive on a freshly created tab and **goes dead after a
reload**. This is the "strange things with reactivity."

### P2 — Two divergent proxies for the same tab.

`manager.state` and `tabs[id]` are never guaranteed to be the *same* proxy object.
For loaded tabs the manager mutates the raw target; `tabs[id]`/`activeTab` reads the
proxy. Vue's dep-tracking fires through the proxy's set trap only, so manager
mutations don't notify `activeTab` readers. (`ViewSelectionDropdown.vue:23` reads
`activeTab?.display`; `setViewMode` mutates the raw state.)

### P3 — Recompute triggering is *inconsistent*: filter is automatic, sort/group is manual.

The verification corrected the original framing here. There are **two** recompute paths:

- **Filter changes recompute automatically.** `CollectionManager.ts:55` wires
  `filterManager.onStateChange → setDirty()`, and `setDirty` (lines 80-105) runs
  `collection.update()` (full filter→sort→group) when active + `autoReload`. So
  `updateFilter`/`addNewFilter`/`deleteFilter` (which emit `onStateChange`) re-run the
  pipeline on their own — which is why `FilterRow.vue:31` / `FilterGroup.vue:31,36,41`
  have their `// props.manager.update(true)` calls **commented out** (redundant).
- **Sort/group changes recompute manually.** `sortManager`/`groupManager`.`onStateChange`
  are **not** wired to `setDirty` (only to save). So every sort/group consumer must call
  `update(true)` / `sortGroups(true)` by hand — `SortForm` (3×), `GroupForm` (5×),
  `PropertyOptions.vue:84,93`, etc.
- **Folder/query changes also recompute manually**, because `setFolders`/`setQuery` don't
  even emit `onStateChange` (P4) → no `setDirty`. Hence `FolderList.vue:71`,
  `TextSearchInput.vue:76`, `ContentFilter.vue:48,54` call `update(true)` explicitly.

Net: **~16 scattered, hand-placed recompute trigger sites**, an automatic filter path that
shadows them, and setters that silently don't recompute. Forget a manual call → stale
results; the commented-out calls show this is already fragile in practice.

**This strengthens B2:** the filter path *already* recomputes automatically off a
state-change signal (`onStateChange`). B2 generalises that one working pattern to sort and
group via per-slice watchers, and deletes the 16 manual calls — it is an extension of an
existing mechanism, not a new invention. (See the double-trigger risk: the existing
`onStateChange → setDirty` wiring must be removed when the filter watch is added.)

### P4 — Setter/notify inconsistency.

`FilterManager.setFolders()` and `setQuery()` mutate state but **do not** emit
`onStateChange` (`FilterManager.ts:573-574`) → those changes never autosave. Most other
setters do emit. There is no single contract.

### P5 — Save fires per keystroke, synchronously, no debounce.

`updateFilter()` → `onStateChange.emit()` → immediate `apiUpdateTabState`. Typing in a
filter value or dragging a slider floods the backend. `uiStore` (the model the user
wants to follow) at least centralises saving in one `watch`, though it too lacks a
debounce.

### P6 — Non-reactive current-tab access + remount hacks.

`getMainTab()` returns a raw `TabManager` from a module global. Components capture it
once (`ViewPanel.vue:19 const currentTab = tabStore.getMainTab()`) and go stale on tab
switch; `TabContainer.vue` works around this with a `show=false → nextTick → reload`
remount toggle. Many call sites do `getMainTab().<x>` with no null guard
(`dataStore.ts:423`, `TabPanel.vue`).

### P7 — Lifecycle leaks / footguns (secondary).

- `deleteTab()` deletes `managers[id]` and removes from `loadedTabs` but **never deletes
  `tabs[id]`** (`tabStore.ts:128-140`) → orphan entry.
- `managers` is a module global, invisible to Pinia/devtools/HMR.
- `loadTabsFromStorage` silently **drops every tab** whose `state.version !==
  TAB_MODEL_VERSION` — bumping the version wipes user tabs with no migration.

---

## 3. Design goals

1. **One reactive source of truth per tab** — the manager state *is* the persisted
   state, with a single proxy identity. No "raw vs proxy" duality, no birth-dependent
   behaviour.
2. **Mutation only through manager functions**, and reactivity (recompute + UI) follows
   automatically from the state change.
3. **Centralised, debounced autosave** modelled on `uiStore` — decoupled from individual
   mutations.
4. **Current-tab access through a wrapper/provider** that resolves the tab once it is
   known and **fully resets descendants on tab change** to eliminate stale captures and
   null races.

---

## 4. Proposed refactor

### Pillar A — Single reactive source of truth

**Make every loaded `TabState` reactive at import, and hand the *same* proxy tree to the
managers and to `tabs[id]`.**

```ts
function importTab(raw: TabState) {
    const tab = reactive(raw)            // wrap ONCE, on the way in
    tabs[tab.id] = tab
    managers[tab.id] = new TabManager(tab) // manager gets the SAME proxy
}
```

Then inside `TabManager`/`CollectionManager`, pass `tab.filterState` (a nested proxy)
to each sub-manager. Invariant to enforce and document:

> `manager.state === tabStore.tabs[id].filterState` (and likewise for sort/group/collection).
> There is exactly one proxy per state slice.

With that invariant:
- `activeTab` (reactive) and `getMainTab().state` read the same object → no P2 divergence.
- Manager update functions mutating `this.state.*` notify every reader.
- There is no second copy. Per Q1 (container), **serialization is just
  `serialize(tabs[id])`** — and because `manager.state === tabs[id].filterState`, that is
  by construction identical to reading off the live managers.

> **Q1 — ✅ RESOLVED → TabState is the container.** Managers hold references into its
> slices (`manager.state === tabs[id].filterState`); serialization reads the TabState
> directly. Smaller diff, matches `buildTabState`.

### Pillar B — Mutation through functions + reactive recompute

Two layers:

**B1 — Make every state mutation go through a manager method with a uniform contract.**
Audit all setters so each one mutates `this.state` *and* signals change consistently.
Fix P4 (`setFolders`/`setQuery` must notify). No setter mutates state silently.

**B2 — Drive *recompute* from the state, not from the caller. The mutator functions
stay.**

A watcher can only replace the **recompute** step. It cannot replace the setters
(`addNewFilter`, `setSort`, `setGroupOption`, …), because each setter does work that a
reactive diff cannot reconstruct:

1. **Identity bookkeeping** — `addNewFilter` → `registerFilter()` mints `filter.id =
   nextIndex()` and inserts into `this.filterIndex`. A watcher seeing "a new object
   appeared in `state.filter.filters`" can't know to assign an id and index it. Filtering
   would still run (it only reads `propertyId/operator/value`), but **UI edit/delete of
   that filter breaks** — forms look filters up by id in `filterIndex`.
2. **Cache invalidation** — `setSort`/`delSort`/`verifyState` → `this._sortCols = null`;
   `FilterManager.verifyState` → `_folderPropId = undefined`.
3. **Guards** — `setSha1Mode` → `if (state.sha1Mode == value) return`.

So the change is **"keep `setX()` as the mutation API; stop making callers also call
`update(true)`"** — the watcher reacts to the state change and recomputes.

**Crucial: it must be per-slice watches mapped to the correct recompute entrypoint — NOT
one deep watch over the tab state.** The forms today don't just call `update()`, they call
the *right* recompute for the change. A single deep watch can't tell these apart and would
run the most expensive path on every change. The mapping the collection must reproduce:

| Change (all mutate `state`) | Correct recompute | Cost |
|---|---|---|
| filter add/edit/delete | `filterManager.update(true)` → filter→sort→group | full pipeline |
| sort add/remove | `sortManager.update(true)` → sort→group | skips filter |
| `groupBy` add/remove | `groupManager.update(true)` → regroup | skips filter+sort |
| group **direction/type** (`options[id]`) | `groupManager.sortGroups(true)` → re-sort groups only | **no regroup** |
| toggle open/close group | nothing (view-state, `onResultChange` only) | none |

Two concrete failures of a naive deep watch:
- **Perf:** changing a group's sort *direction* (`state.options[id].direction`) would
  trigger a full `group()` rebuild instead of the cheap `sortGroups()`. On 1M rows that is
  exactly the regression [[managers_1m_optimization]] avoids.
- **View-state clobber:** `GroupState` is only `{ groupBy, options, sha1Mode }` — open/closed
  fold (`GroupView`), selection, and custom groups live in the **result tree**, not in
  `state`. A spurious `group()` rebuild from over-triggering resets that transient state.

**The CollectionManager is the single orchestrator — the watches live there, not in the
sub-managers.** It already plays this role today (`setDirty → update()`), but only
`filterManager.onStateChange` is wired to it (`CollectionManager.ts:55`). B2 generalises that
to all three slices via state watches, each mapped to the right entrypoint:

```ts
// CollectionManager — the ONE place that decides whether/what/when to recompute.
// Generalises the existing setDirty pattern from filter to sort + group.
watch(() => filterState,        () => this.requestReload('filter'),     { deep: true })
watch(() => sortState,          () => this.requestReload('sort'),       { deep: true })
watch(() => groupState.groupBy, () => this.requestReload('group'))
watch(() => groupState.options, () => this.requestReload('sortGroups'), { deep: true })
// groupState.sha1Mode → 'group'

requestReload(kind: ReloadKind) {
    this.runState.isDirty = true
    if (!this.runState.active || !this.state.autoReload) return  // load + manual-reload handled here
    this.pending = maxKind(this.pending, kind)                   // order: filter > sort > group > sortGroups
    this.debouncedRun()                                          // runs ONE entrypoint, in order
}
```

The collection maps each `kind` to a pipeline entrypoint it already owns — `'filter'` → full
`update()`; `'sort'` → re-sort the current filter result then regroup (the `onSort` path);
`'group'` → regroup `sortManager.result.slots`; `'sortGroups'` → `groupManager.sortGroups()`.
Sub-managers keep their mutators and their `update()/sort()/group()` methods; they just stop
being the trigger point.

**What moves and what stays:**
- **Moves to the CollectionManager:** the trigger. The scattered `update(true)` /
  `sortGroups(true)` calls in forms **and** the `filterManager.onStateChange → setDirty`
  wiring (`:55`) are all replaced by the four state watches above.
- **One orchestrator, one ordering.** All four watches feed one `requestReload`, so the
  collection coalesces them itself (a `groupBy` add also writes `options` → both fire → it
  keeps the most expensive, `group`) and runs the pipeline in the right order. **No
  per-manager scheduler**, and no reliance on the `onResultChange` cascade for ordering —
  `update()` already calls filter→sort→group inline.

**Async-race is a non-issue here (demoted from a hard constraint):**
- Interactively, changes are **sequential** (one user action at a time) and the collection
  serialises them through the single `requestReload`/`run` path.
- At **load**, tabs import **deactivated** (`importTab → manager.deactivate()`,
  `tabStore.ts:52`), so the bulk state assignment hits `!active` → marks `isDirty` only, no
  recompute. `selectMainTab` then does `activate()` + a single `await update()`
  (`:149-151`). The "many changes at once" moment yields exactly one run.
- Only residual: a *slow* async run (first-time `requireFullColumn`, plugin/text query)
  outrun by a fast second action. Cover with a one-line monotonic token at the single
  collection `update()` — `const t = ++this.runToken; …await…; if (t !== this.runToken) return`.
  Cheap insurance, not architecture.

**Remaining real constraints:**
- **Debounce** `requestReload`/`run` so filter-value typing / slider drags coalesce.
- **`immediate: false`** + the existing `col.isReady` gate so watch setup / load doesn't
  recompute before columns exist.
- **Respect `autoReload`** — `requestReload` early-returns when the user disabled auto-reload,
  exactly as `setDirty` does today.

> **Q2 — ✅ RESOLVED → B2, orchestrated by the CollectionManager.** Keep mutators; replace
> the manual `update()` with deep watches *on the CollectionManager* (one per slice → its
> entrypoint), coalesced/ordered/gated in one `requestReload`. Trigger mechanism = deep watch
> (Q5). The collection is the single owner of update ordering.

### Pillar C — Centralised, debounced autosave (the `uiStore` model)

Delete the per-emit save chain (`saveManagerStates → saveState → apiUpdateTabState`).
Replace with **one debounced deep watch on the active tab** (Q3), re-pointed on switch:

```ts
// single active-tab autosave; re-armed whenever mainTab changes
let stopSave: WatchStopHandle | null = null
let flush: () => void = () => {}

watch(mainTab, (id, prevId) => {
    flush()              // flush-on-switch: persist the tab we're leaving
    stopSave?.()
    if (!id) return
    const debounced = debounce(() => apiUpdateTabState(id, serialize(tabs[id])), 400)
    flush = () => debounced.flush()
    stopSave = watch(() => tabs[id], () => { if (tabStore.loaded) debounced() }, { deep: true })
}, { immediate: true })
```

Notes:
- Debounce (≈300–500ms) collapses keystroke/slider floods (fixes P5).
- Because state is now reliably reactive (Pillar A), the deep watch actually fires for the
  loaded tab — today it would not.
- `runState`/`result` (transient, slot arrays) must be **excluded** from `serialize()` —
  only persist the `*State` slices. Keep transient runtime fields off the `TabState`
  object, or serialize a whitelist (and `toRaw`/`deepCopy` before sending).
- Per Q3, background tabs are not watched; their reconciled state persists on next activate.
  `deleteTab`/`clear` must call `stopSave?.()` + `flush()`.

### Pillar D — `TabProvider` wrapper + `useCurrentTab()`

Formalise the existing `TabContainer` remount hack into a real provider:

```vue
<!-- TabProvider.vue -->
<template>
  <div v-if="tabStore.loaded && manager" :key="tabId">
    <slot :tab="manager" />
  </div>
</template>
```

- Resolve the `TabManager` once the active id is known; `provide()` it (and/or its
  reactive state) so descendants `inject` via a `useCurrentTab()` composable instead of
  calling `tabStore.getMainTab()`.
- **`:key="tabId"`** forces a full remount of the subtree on tab change → no stale
  `const currentTab = getMainTab()` captures, no null-window races (fixes P6). This
  replaces the manual `show`/`nextTick` toggle.
- `getMainTab()` can remain for non-component callers (e.g. `dataStore`), but should be
  null-guarded and ideally returned as a `computed`/reactive ref.

> **Q4 — ✅ RESOLVED → provide the full `TabManager`.** Descendants `inject` it via
> `useCurrentTab()`; existing `tab.collection.groupManager` (29×) / `filterManager` (21×)
> call sites keep working unchanged.

### Pillar E — Lifecycle fixes (fold in while touching this code)

- `deleteTab`: also `delete tabs[id]` and tear down its autosave watcher.
- Move `managers` into the store's reactive state (or a `shallowReactive` map) so it is
  not a module global; clears HMR/devtools issues.
- Per Q9: on `version` mismatch in `loadTabsFromStorage`, **warn + reset** the tab to a
  fresh `buildTabState()` (explicit, logged) instead of silently dropping it. No migrators.

### Pillar F — Per-view state inside a single tab (NEW requirement)

**Today** the split is cosmetic: `views/MainView.vue` renders two `<ViewPanel />` in a
`SplitLayout`, but *both* panes call `getMainTab()` and read the **same**
`state.display` + `state.imageSize` → identical render. The split flag lives in
`uiStore.panelStates.viewSplitEnabled`, **not** in the tab.

**Target:** a tab owns **1–2 views**; each view has its own type + display options; the
split flag moves into the tab.

```ts
interface ViewState {                          // per-view (Q11: ONLY these three)
    type: 'tree' | 'grid' | 'graph' | 'map'    // was TabState.display
    imageSize: number                          // was TabState.imageSize (per-view!)
    mapOptions: MapOptions                      // map-only display options, per-view
}

interface TabState {
    version: number; id: string; name: string
    splitView: boolean             // was uiStore.viewSplitEnabled — false = show view1 only
    splitRatio: number             // was uiStore.mainSplitRatio — now per-tab (Q13)
    views: [ViewState, ViewState]  // fixed pair; view2 shown only when splitView (Q12)

    // SHARED across both views — one collection pipeline per tab (Q10):
    collectionState; filterState; sortState; groupState
    // SHARED tab-level (Q11): visibleProperties, propertyOptions, selectedFolders,
    //   visibleFolders, isSelection, ...
}
```

**Key structural consequence — the recompute/display split falls out cleanly:**

| State | Scope | On change → |
|---|---|---|
| `filterState` / `sortState` / `groupState` | **tab** (shared by both views) | recompute (Pillar B2) + autosave |
| `views[i].type` / `imageSize` / `mapOptions` | **per-view** | **autosave only — no recompute** (collection already computed; just a display swap) |

So switching view1 tree→grid or dragging its image-size slider must **not** trigger
filter/sort/group. Per-view options get an autosave watch but no recompute watch — this
actually *reinforces* B2's per-slice granularity (display slices simply have no recompute
watcher).

**Component impact (extends Pillar D):**
- `ViewPanel` takes a `viewIndex` prop (primary = 0, secondary = 1) and reads
  `tab.state.views[viewIndex]` instead of the shared `state.display` / `state.imageSize`.
- `views/MainView.vue` drives `:hide-secondary="!tab.state.splitView"` from the **tab**,
  not `uiStore`. `ViewSelectionDropdown` (currently reads `activeTab.display`) sets
  `views[viewIndex].type`.
- `TabManager` still owns **one** `CollectionManager` shared by both views (Q10). The
  scrollers already bind `tab.collection.groupManager`, so the shared-pipeline path is
  unchanged.
- Migrate `viewSplitEnabled` **and** `mainSplitRatio` out of `uiStore` into
  `TabState.splitView` / `TabState.splitRatio` — each tab remembers its own split geometry
  (Q13). `views/MainView.vue` reads `secondary-ratio` / `hide-secondary` from the tab.

This also bumps `TAB_MODEL_VERSION` (old `display`/`imageSize` → `views[]`); per Q9 that
means warn + reset, so no migrator needed.

**Migration surface (measured — Pillar F is the most call-site churn):**
- `tab.state.mapOptions` — **~23 sites** (map components). All must take a `viewIndex` /
  the view's `ViewState` and read `views[i].mapOptions`. Largest single chunk.
- `tab.state.display` — **~12 sites** → `views[i].type`.
- `*.imageSize` reads — **~35 matches** (includes `mapOptions.imageSize` and unrelated
  `tab.imageSize`); the tab-level ones → `views[i].imageSize`.
- `views/MainView.vue` + `components/mainview/MainView.vue` + `ViewPanel.vue` all read
  `state.display`/`state.imageSize` today — every pane renderer must thread `viewIndex`.

Practically: introduce `useCurrentView(index)` (built on `useCurrentTab()`) returning the
view's `ViewState`, and migrate the display/map/imageSize reads to it. This is mechanical
but broad — keep it as its own step (sequencing #6).

---

## 5. Suggested sequencing

1. **Pillar A** — reactive-on-import + shared-proxy invariant. *Unblocks everything,
   low behavioural risk, fixes P1/P2 immediately.*
2. **Pillar C** — swap per-emit save for debounced deep watch; delete the old chain.
   *Depends on A (watch must fire for loaded tabs).*
3. **Pillar D** — `TabProvider` + `useCurrentTab`, migrate `getMainTab()` call sites,
   add `:key` remount. *Independent of B.*
4. **Pillar B2** — granular per-slice watchers (keep mutators, remove manual `update()`
   calls) + coalescing scheduler + active-gate/debounce/race-guard. *Largest; do last,
   behind verification.*
5. **Pillar E** — lifecycle/version fixes. *Opportunistic, any time.*
6. **Pillar F** — per-view `ViewState` model + move split into the tab. *Depends on A
   (model lives in the reactive TabState) and pairs with D (`ViewPanel` viewIndex). Bumps
   `TAB_MODEL_VERSION`.*

Each step is independently shippable and testable.

---

## 6. Open questions — all resolved

- **Q1 — ✅ RESOLVED → TabState is the container.** Managers reference into its slices.
- **Q2 — ✅ RESOLVED → Granular watchers (B2), orchestrated by the CollectionManager.** Keep
  mutators, drop manual `update()`; the collection watches each slice → its entrypoint and is
  the single owner of update ordering (generalised `setDirty`). See §4 Pillar B2.
- **Q3 — ✅ RESOLVED → Active tab only + flush-on-switch.** Watch the main tab; flush on
  switch. Background tabs persist on next activate (self-heals via `verifyState` on load).
- **Q4 — ✅ RESOLVED → provide the full `TabManager`** via `useCurrentTab()`. Least churn.
- **Q5 — ✅ RESOLVED → Deep watch.** One `{deep:true}` watch per persisted slice. Fine
  because the watched slices are small config, not the row data. Still requires a
  serialized whitelist for autosave (exclude `result`/`runState`) and the collection-level
  coalescing noted in §0.
- **Q6 — ✅ RESOLVED → persist nothing transient.** `result`, `runState`, group fold
  (`GroupView`), selection, and custom groups are runtime-only and excluded from
  serialization. Folds + selection reset on reload; recompute rebuilds freely.
- **Q7 — ✅ RESOLVED (matches current).** Only the active tab recomputes; background tabs
  mark `runState.isDirty` and recompute lazily on activate, as `selectMainTab` does today.
- **Q8 — ✅ RESOLVED → singular main tab.** Provider keys on one `mainTab`; one active
  manager. Distinct-tab-per-pane split view is out of scope.
- **Q9 — ✅ RESOLVED → warn + reset.** On `version` mismatch, log a warning and reset the
  tab to `buildTabState()`. No migrators.

### New questions from the per-view model (Pillar F)

- **Q10 — ✅ RESOLVED → shared.** One `CollectionManager` per tab; both views display the
  same filter/sort/group result. Shared selection + group folds across panes.
- **Q11 — ✅ RESOLVED → only `type` + `imageSize` + `mapOptions` per-view.** Everything else
  stays tab-level/shared.
- **Q12 — ✅ RESOLVED → fixed pair** `views: [ViewState, ViewState]`; `splitView` toggles
  view2 visibility.
- **Q13 — ✅ RESOLVED → move to tab.** `splitView` + `splitRatio` both in `TabState`;
  migrate out of `uiStore`.

*All open questions (Q1–Q13) resolved — ready to implement per §5 sequencing.*

---

## 7. Risks

- **Reactivity perf:** deep watches over filter/group state + result chains on 1M-row
  collections — must preserve the active-gate and debounce. (See [[managers_1m_optimization]].)
- **Double-trigger (concrete):** filter recompute is *already* automatic via
  `filterManager.onStateChange → setDirty` (`CollectionManager.ts:55`). When B2 adds the
  collection's `filterState` watch, that wiring **must be removed** or every filter change
  recomputes twice. Likewise the old `onStateChange → saveManagerStates` save chain must be
  deleted when the autosave watch (C) lands, or saves fire from both. Replace each trigger
  wholesale; don't half-wire.
- **Serialization of proxies:** `apiUpdateTabState` must send plain JSON
  (`deepCopy`/`toRaw`) — sending a reactive proxy will bloat/break the payload. (Note:
  `result`/`runState` are NOT in `TabState`, so a deep watch on `tabs[id]` already won't
  see them; the rule is "never stuff transient fields into `TabState`.")
- **Pillar F call-site churn:** ~23 `mapOptions` + ~12 `display` + many `imageSize` reads
  move per-view. Mechanical but broad; isolate as its own step and lean on
  `useCurrentView(index)`.
- **`autoReload` interaction:** `setDirty` only recomputes when `state.autoReload` is true.
  B2 watchers should respect the same flag (don't recompute when the user has disabled
  auto-reload), else B2 changes behaviour for that mode.
