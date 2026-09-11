---
tags: [inventory, frontend]
zone: core-engine
---
# 03 · Collection engine (`src/core`)

Back to [[00 Frontend inventory]] · Unused files: [[99 Unused files]]

**Scope:** the pure TypeScript engine that turns a collection (filter → sort → group → cluster) into the tree the views render. There's one `CollectionManager` per `collectionId`, and a `TabManager` owns the views. The docs are in `notes/group_manager_redesign_plan.md`, `notes/managers_optimization_audit.md` and `notes/sha1_mode_flat_piles_optimization.md`.

## Zone-level checks
- [ ] `GroupManager.ts` (821 L, 26 importers) is the planned split target (engine / result / `ClusterManager`). Check which importers only need `GroupInspector` (`group/inspector.ts`) and could depend on that instead.
- [ ] `FilterManager.ts` (722 L) uses a bitmask filter core. Check the operators against every `PropertyType`.
- [ ] `group/types.ts` is meant to stay dependency-free ("only leaf modules + @/data"). Check that it hasn't picked up imports.
- [ ] The auto-reload state (`collection.setAutoReload`, `runState.isDirty`) no longer has a UI toggle, because `ToggleReload.vue` is dead. Keep it, or remove it?
- [ ] These modules are pure TS, so they can be run headless with esbuild + node, no browser needed.

## Files: managers
- [ ] `src/core/TabManager.ts` · 232 L. One `CollectionManager` per `collectionId`; two views that share an id share the collection. Holds the view state and visible properties.
- [ ] `src/core/CollectionManager.ts` · 344 L. Runs the pipeline (filter → sort → group), tracks run state and dirty flag, reload kinds, auto-reload.
- [ ] `src/core/FilterManager.ts` · 722 L. Bitmask filter core, the filter-group tree, operators (`availableOperators`, `operatorHasInput`), folder filter, text query.
- [ ] `src/core/SortManager.ts` · 484 L. Multi-property sort, `ImageOrder`, `sortParser`.
- [ ] `src/core/GroupManager.ts` · 821 L. Builds the group tree by property, date buckets and custom groups, and hands out iterators and navigators.
- [ ] `src/core/sha1Piles.ts` · 83 L. The sha1 "piles" display overlay for sha1 mode: `computeSha1Piles`, `pileSlots`…

## Files: `core/group/`
- [ ] `src/core/group/types.ts` · 138 L. `GroupType`, `GroupState`, `Group`, `GroupView`, `ClusterParam`, `GroupTree`…
- [ ] `src/core/group/builders.ts` · 38 L. Factories: `buildGroup`, `buildRoot`, `buildGroupOption`, `createGroupState`.
- [ ] `src/core/group/valueParser.ts` · 24 L. Per-type value normaliser used when bucketing.
- [ ] `src/core/group/valueIndex.ts` · 37 L. `GroupValueIndex`: a persistent value-key → stable-id map.
- [ ] `src/core/group/dateBuckets.ts` · 44 L. Date bucket arithmetic, with no Date allocations in the scan loop.
- [ ] `src/core/group/sort.ts` · 65 L. Orders a group's children by property value or by size.
- [ ] `src/core/group/groupOps.ts` · 248 L. Runtime tree edits: custom groups, move images, rename, split, clear.
- [ ] `src/core/group/GroupResult.ts` · 155 L. The computed tree plus its index.
- [ ] `src/core/group/GroupIterator.ts` · 303 L. `GroupIterator` / `ImageIterator`: read-only navigators over the display order. Pile-aware.
- [ ] `src/core/group/GroupNavigator.ts` · 163 L. Keyboard and next/previous navigation over groups.
- [ ] `src/core/group/inspector.ts` · 56 L. `GroupInspector`: the tree-inspection contract that the scrollers, the map and the charts render against.
- [ ] `src/core/group/ClusterManager.ts` · 396 L. Cluster requests and runs (through `actionStore`), attaching clusters as custom groups. Also used by `MapView`.
