# Mission: Separate cluster logic from GroupManager

## Goal

Make the code simpler and more maintainable through separation of concerns:

- **GroupManager** becomes a pure engine: sorted slots + groupBy state → property tree. No cluster knowledge.
- **Clusters** get their own source of truth (a registry), applied to the tree as an overlay.
- **A final result object** owns the composed tree, its indexes and its iterators.
- **A collection-level API** lets any caller cluster a group directly by group id + function params.

## Current problems (as of rework-front branch)

- Clusters live in `GroupManager.customGroups` and are grafted into the property tree via `addCustomGroups`. On every rebuild, `group()` replays them with a fixed-point `while (insert)` loop — a symptom that clusters don't belong to the rebuild lifecycle.
- Cluster special-cases are scattered through `updateSelection` (`type == Cluster` skips, `dropMembership` exemption, sort exemption). `moveImagesToGroup` is cluster-only surgery living in the generic manager.
- Orchestration is inverted: `actionStore.executeAction` returns converted `Group[]`, then **three UI components** (`GroupLine.vue`, `ClusterLine.vue`, `ClusterView.vue`) each wire the result in with `manager.addCustomGroups(groupId, groups, true)` themselves.

## Design decisions

### 1. Compose into one final tree, keep two sources of truth

The tree-traversal complexity concern only applies if traversal must consult two structures. It doesn't have to:

- `ClusterRegistry`: `Map<groupId, ClusterSet>` where `ClusterSet = { groups, function, inputs, timestamp }`. Pure data — no parent/depth/order.
- A **compose step** applies the registry to the property tree after each rebuild, producing a single final tree. Traversal, iterators, `orderedIds`, `imageToGroups` stay exactly as simple as today.
- The ad-hoc replay loop becomes a deterministic "apply overlays" pass.

### 2. Extract the result object (`GroupResult` / `ViewTree`)

Move out of GroupManager: `index`, `imageToGroups`, `orderedIds`, `buildOrdinalRanges`, `GroupIterator`/`ImageIterator`, the version tick.

Pipeline: `propertyTree + clusterRegistry (+ sha1Mode) → GroupResult`.

Note: sha1 grouping is *already* a display overlay done the same messy inline way — it gets the same home as clusters, which validates the abstraction.

`moveImagesToGroup` becomes a ClusterRegistry mutation + recompose. Cluster special-cases fall out of `updateSelection` naturally (property updates never touch the registry).

### 3. Orchestration on CollectionManager, not actionStore

`actionStore` stays an RPC layer (call backend function, convert result) with no view/collection knowledge. The use-case lives on the owner of the groupManager:

```ts
// CollectionManager
async clusterGroup(groupId: number, funcId?: string, params?: ...) {
    const group = this.result.get(groupId)
    const ctx = { instanceIds: /* group slots → ids */, uiInputs: ... }
    const { groups } = await actions.executeAction(funcId ?? defaults.group, 'group', ctx, inputs)
    this.clusters.set(groupId, { groups, function: funcId, inputs })
    this.recompose()
}
```

"Which collection" is answered by *who you call*, not by a parameter actionStore must resolve. Kills the three duplicated wiring sites.

### 4. Cleanup

Delete from GroupManager: `customGroups`, the replay loop, `addCustomGroups`/`delCustomGroups`/`clearCustomGroups` (become registry ops + recompose), cluster branches in `updateSelection`.

## Recommended sequence

**2 (result object + compose step) → 4 (strip cluster code from GroupManager) → 3 (collection-level clusterGroup API)**

Doing the API last means it lands on the clean structure instead of wrapping the old one. (Alternative: do 3 first for quick value — it's mostly moving call sites — but the real simplification is in 2 → 4.)

## Open question

Should cluster sets survive a re-group (groupBy change)? Today they're dropped (`setGroupOption` resets `customGroups`) but survive re-sorts via the replay loop. With a registry keyed by stable group IDs (`GroupValueIndex` keeps IDs stable across rebuilds), the policy becomes explicit — e.g. keep clusters whose parent group still exists, drop the rest — instead of emergent from the replay loop.
