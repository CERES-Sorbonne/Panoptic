---
tags: [inventory, frontend]
zone: core-engine
---
# 03 · Collection engine (`src/core`)

Back to [[00 Frontend inventory]] · Unused files: [[99 Unused files]]

**Scope:** the pure TypeScript engine that turns a collection (filter → sort → group → cluster) into the tree the views render. There's one `CollectionManager` per `collectionId`, and a `TabManager` owns the views.

*Refreshed 2026-09-21 (line counts and file list at `5a6893b9`).* The live docs for this zone are **`notes/refactor/`** — start at its `README.md`; `notes/group_manager_redesign_plan.md`, `notes/managers_optimization_audit.md` and `notes/sha1_mode_flat_piles_optimization.md` are the older background.

## Zone-level checks
- [x] ~~`GroupManager.ts` is the planned split target (engine / result / `ClusterManager`).~~ **Done** — see `notes/refactor/collection_inspection_mission.md`. `GroupManager` is the property-tree engine, `GroupResult` the result + `IteratorHost`, `ClusterManager` the cluster ops, `ClusterOverlay` the authored membership, and the scrollers now take a `GroupInspector` rather than a manager.
- [ ] `FilterManager.ts` (721 L) uses a bitmask filter core. Check the operators against every `PropertyType`.
- [ ] `group/types.ts` is meant to stay dependency-free ("only leaf modules + @/data"). Check that it hasn't picked up imports.
- [ ] The auto-reload state (`collection.setAutoReload`, `runState.isDirty`) no longer has a UI toggle, because `ToggleReload.vue` is dead. Keep it, or remove it?
- [x] ~~These modules are pure TS, so they can be run headless with esbuild + node.~~ **Done, and committed**: `npm test` (136 tests) and `npm run test:sim` run this zone under `node --test` against the stubs in `test/group/harness/`. See `test/group/README.md`.

## Files: managers
- [ ] `src/core/TabManager.ts` · 232 L. One `CollectionManager` per `collectionId`; two views that share an id share the collection. Holds the view state and visible properties.
- [ ] `src/core/CollectionManager.ts` · 362 L. Runs the pipeline (filter → sort → group), tracks run state and dirty flag, reload kinds, auto-reload.
- [ ] `src/core/FilterManager.ts` · 721 L. Bitmask filter core, the filter-group tree, operators (`availableOperators`, `operatorHasInput`), folder filter, text query.
- [ ] `src/core/SortManager.ts` · 483 L. Multi-property sort, `ImageOrder`, `sortParser`.
- [ ] `src/core/GroupManager.ts` · 1020 L. Builds the group tree by property, date buckets and custom groups, and hands out iterators and navigators.
- [ ] `src/core/sha1Piles.ts` · 98 L. The sha1 "piles" display overlay for sha1 mode: `computeSha1Piles`, `pileSlots`…

## Files: `core/group/`
- [ ] `src/core/group/types.ts` · 144 L. `GroupType`, `GroupState`, `Group`, `GroupView`, `ClusterParam`, `GroupTree`…
- [ ] `src/core/group/builders.ts` · 37 L. Factories: `buildGroup`, `buildRoot`, `buildGroupOption`, `createGroupState`.
- [ ] `src/core/group/valueParser.ts` · 41 L. Per-type value normaliser used when bucketing.
- [ ] `src/core/group/valueIndex.ts` · 48 L. `GroupValueIndex`: a persistent value-key → stable-id map.
- [ ] `src/core/group/dateBuckets.ts` · 43 L. Date bucket arithmetic, with no Date allocations in the scan loop.
- [ ] `src/core/group/sort.ts` · 67 L. Orders a group's children by property value or by size.
- [ ] `src/core/group/groupOps.ts` · 221 L. Runtime tree edits: custom groups, move images, rename, split, clear.
- [ ] `src/core/group/GroupResult.ts` · 154 L. The computed tree plus its index.
- [ ] `src/core/group/GroupIterator.ts` · 335 L. `GroupIterator` / `ImageIterator`: read-only navigators over the display order. Pile-aware.
- [ ] `src/core/group/GroupNavigator.ts` · 191 L. Keyboard and next/previous navigation over groups.
- [ ] `src/core/group/inspector.ts` · 58 L. `GroupInspector`: the tree-inspection contract that the scrollers, the map and the charts render against.
- [ ] `src/core/group/ClusterManager.ts` · 304 L. Cluster requests and runs (through `actionStore`), plus every cluster op; membership itself lives in `ClusterOverlay`. Also used by `MapView`.
- [ ] `src/core/group/ClusterOverlay.ts` · 738 L. The authored side of the cluster view: one `ClusterContainer` per clustered bucket, holding a dense `slot → node index` map (`owner`) and the node table that shapes the cluster subtree. A cluster group's `slots` is derived from it by `resync` after every rebuild, so a filter, sort or reload cannot lose a pile. Epoch-guarded against `columnStore` slot re-minting; `checkInvariants` runs in dev builds.
- [ ] `src/core/group/slotOrder.ts` · 79 L. Puts a group's slots back in display order after an incremental edit (sorted prefix + short appended tail), instead of re-sorting the array. No imports, to stay out of the cycle.
- [ ] `src/core/group/groupSlots.ts` · 24 L. The slots a group effectively holds, sub-piles included. Its own file with a type-only import so the selection surface doesn't pull in the store chain.
- [ ] `src/core/group/convertGroupResult.ts` · 83 L. Turns a plugin/action `GroupResult` (score lists, sha1 → instances) into `Group` nodes for the tree.
- [ ] `src/utils/debugGroup.ts` · 43 L. Grouping diagnostics: traces a value edit from the data delta into the group tree. Off in production, on in dev, and `window.__grpDebug` overrides either way. Costly log arguments belong inside `if (grpDebugOn())`.
