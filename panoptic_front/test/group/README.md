# Grouping / clustering regression suite

Headless tests over the **real** `src/core/GroupManager`, `ClusterManager`, `ClusterOverlay`,
`GroupIterator`, `GroupNavigator` and the `group/*` helpers. Nothing under test is reimplemented
here — only the pinia stores underneath are stubbed.

## Running

```sh
npm test          # builds the bundles, then runs the suite with node --test
npm run test:sim  # the randomised simulation (see below)
```

Node 24 strips types on its own, but it cannot run these modules directly: they use the `@/`
alias, extensionless relative imports and `import.meta.env`, and `@/data/stores/*` are pinia
stores that drag in the router and axios. So `build.mjs` bundles the suite with the project's own
**vite** (no extra dependency), aliasing those three stores to `harness/stubs/` and pinning
`import.meta.env.DEV` to `true` so `ClusterOverlay.checkInvariants` (I1–I5) runs.

`build.mjs` emits two entries: `suite.mjs` (node:test) and `sim.mjs` (the standalone
simulation). Output goes to `test/group/.build/` (git-ignored). The suite runs in well under a
second.

## Layout

| path | what it is |
| --- | --- |
| `suite.ts` | the single entry point; imports the hooks, then every spec |
| `build.mjs` | the vite bundle step |
| `harness/hooks.ts` | root hooks: clean console per test, **fail on any I1–I5 breach** |
| `harness/console.ts` | console capture (`invariantBreaches`, `capturedWarnings`) |
| `harness/world.ts` | fixtures (`groupedBy`, `ungrouped`, `handTree`) + the tree invariants |
| `harness/stubs/*` | headless `columnStore` / `dataStore` / `actionStore` / `vue-router` |
| `specs/*` | one file per fix |
| `sim/*` | the randomised model-based simulation |

`harness/world.ts` holds the two predicates most specs lean on:

- `i2gProblems(m)` — `imageToGroups` names exactly the tree **leaves** displaying each instance,
  with no empty `Set` left behind.
- `coverageProblems(m)` — every slot the root holds is displayed by exactly one leaf.

The `afterEach` hook in `harness/hooks.ts` fails **any** test that provoked a `[ClusterOverlay]`
invariant report, so every cluster test carries the I1–I5 checks for free.

## Coverage map

| fix | spec file | tests |
| --- | --- | --- |
| **A1** one "no value" key per type | `specs/a1_valueParser.ts` | `A1 valueParser[...]`, `A1 isNoValue`, `A1 integration: ...` |
| **A2** a real removal bumps `version` | `specs/a2_version.ts` | `A2: ...` |
| **A3** group selection over `groupSlots` | `specs/a3_groupSlots.ts` | `A3 groupSlots: ...`, `A3: ...` |
| **A4** an iterator for a missing id is a dead end | `specs/a4_iterators.ts` | `A4: ...` |
| **A5** a view must not wipe collection state | `specs/a5_staticChecks.ts` | `A5: ...` (static source check — see below) |
| **A6** `setAsRoot` is gone | `specs/a6_setAsRoot.ts` | `A6: GroupManager has no setAsRoot` |
| **A7** `isCurrent` is false for an unresolved iterator | `specs/a7_isCurrent.ts` | `A7: ...` |
| **A8** `computeSha1Piles` survives a sha1-less slot | `specs/a8_sha1Piles.ts` | `A8: ...` |
| **A9** `imageToGroups` holds only leaves | `specs/a9_imageToGroups.ts` | `A9: ...` |
| **A10** dead vs detached cluster nodes | `specs/a10_deadNodes.ts` | `A10: ...` |
| **A11** cluster runs have a lifetime | `specs/a11_clusterRuns.ts` | `A11: ...` |
| **A12** an arrival reaches `root.slots` | `specs/a12_newArrivals.ts` | `A12: ...` |
| **B2** `orderSlots` == the reference sort | `specs/b2_orderSlots.ts` | `B2: ...` |
| **B4** scoped `applySha1Piles` == a full rebuild | `specs/b4_sha1PileScope.ts` | `B4: ...` |
| **B5** `resync` reports real change only | `specs/b5_resync.ts` | `B5: ...` |
| **B6** the incremental path records a group's `key` | `specs/b6b7_keysAndPruning.ts` | `B6: ...` |
| **B7** `valueIndex.delete` / `imageToGroups` pruning | `specs/b6b7_keysAndPruning.ts` | `B7: ...` |
| **C1** `sortGroups` re-derives `order` / `orderedIds` | `specs/c_simFindings.ts` | `C1: ...` |
| **C2** un-clustering gives a bucket its `imageToGroups` back | `specs/c_simFindings.ts` | `C2: ...` |
| **C3** a shift anchor is checked with `isCurrent` | `specs/c_simFindings.ts` | `C3: ...` |
| **C4** `isCurrent` is false once a group has children | `specs/c_simFindings.ts` | `C4: ...` |
| **D1** an unregistered tag id is not a value | `specs/d1_tagRegistry.ts` | `D1: ...` |
| **D2** a tag deletion the view survives | `specs/d2_tagDeletion.ts` | `D2: ...` |
| **E1** appending a level moves the clusters down | `specs/e1_appendLevel.ts` | `E1: ...` |
| DEV invariants I1–I5 | `specs/invariants.ts` + `harness/hooks.ts` | `invariants: ...` |
| the simulation, smoke-sized | `specs/sim_smoke.ts` | `sim: 3 runs x 50 ops ...` |

`B2` seeds its randomised trials with a fixed seed (`0x5eed1234`), printed in the test name.

## Notes on what is not covered

- **A5** is a Vue `onMounted` change. Mounting a component headlessly costs more machinery than
  the check is worth, so it is asserted statically instead: no component in `src/components`
  calls `clearCustomGroups`, and `GridScroller.onMounted` builds its first window with
  `computeLines()`.

---

# The simulation (`sim/`)

The suite above locks in bugs somebody already found. The simulation looks for the ones nobody
has: it drives the real `GroupManager` / `ClusterManager` / `ClusterOverlay` through long
sequences of randomised, realistic operations and checks every invariant after **every single
step**.

```sh
npm run test:sim                       # 150 runs x 400 ops over 6/16/40/90 instances (~5s)
SIM_SEED=123456 npm run test:sim       # replay exactly that run
SIM_RUNS=600 SIM_STEPS=700 npm run test:sim
```

| variable | meaning | default |
| --- | --- | --- |
| `SIM_SEED` | base seed; with it set, `SIM_RUNS` defaults to 1 | random (printed) |
| `SIM_RUNS` | runs in the batch (seed = base + index) | 150 |
| `SIM_STEPS` | operations per run | 400 |
| `SIM_INSTANCES` | fixture size | rotates 6 / 16 / 40 / 90 |
| `SIM_SHRINK_MS` | shrink budget per failure, 0 to disable | 8000 |
| `SIM_QUIET` | only the summary and the failures | off |

## How it is built

| file | what it is |
| --- | --- |
| `sim/rng.ts` | mulberry32 — a run is a seed and nothing else |
| `sim/model.ts` | the **reference model**: values per instance + filter / sort / groupBy, and the bucket keys they imply, written out the obvious way |
| `sim/world.ts` | the model beside a real `GroupManager`; does what `CollectionManager` does between a state change and the engine, minus the debounce |
| `sim/ops.ts` | the operation catalogue |
| `sim/check.ts` | the invariants |
| `sim/runner.ts` | run, replay, shrink, report |
| `sim/main.ts` | the `npm run test:sim` entry |

An operation is split in two: `plan` consumes the RNG and returns a plain serialisable record,
`apply` executes it and consumes no randomness at all. A plan names its targets by **position
among the current candidates**, so dropping one operation leaves every later one executable —
which is what makes the delta-debugging shrinker work. A failure prints the seed, the broken
invariants and the shortest operation log that still breaks the same one; 200-operation logs
routinely shrink to one or two lines.

Cluster membership is deliberately **not** modelled: it is authored, not derivable. The
simulation checks the overlay's structural rules instead.

## What it drives

`setValues` (all six property kinds, unset included) · `addArrivals` (the A12 path) ·
`delInstances` · `groupAdd` / `groupAppend` / `groupDel` / `groupReorder` (0 to 3 levels;
`groupAppend` goes through `setGroupOption` alone, so the clusters move down instead of clearing) · `groupOption`
(`stepSize`, `stepUnit`, direction, `GroupSortType`) · `filterChange` · `sortChange` ·
`sha1Toggle` · `clusterLeaf` (directly, through a real `cluster()` action run, or as the empty
bucket) · `clusterStartAsync` / `clusterFinishAsync` (a clustering left in flight while the tree
keeps changing) · `subCluster` · `delCustom` · `mergePiles` · `deletePile` · `moveImages` ·
`drain` (value write first, as the view does it) · `clearCustom` · `toggleOpen` ·
`selectGroup` / `selectImage` (shift-range included) · `clearSelection` / `toggleAll` ·
`fullUpdate` · `regroup`.

## What it asserts, after every step

- **membership** — every present instance is displayed under exactly the bucket key paths the
  reference model derives, once each; nothing filtered out or deleted is displayed
- **root** — `root.slots` is the collection: every present slot once, nothing else
- **tree** — everything in `result.index` is reachable from the root and registered under its
  own id, `parent` / `parentIdx` / `depth` agree, no group holds a slot twice, no attached leaf
  is empty, `subGroupType` is the children's common type and `undefined` iff they are mixed
- **i2g** — `imageToGroups` names exactly the leaves displaying each instance, with no empty
  `Set` left behind (the same predicate the A9 spec uses)
- **order** — `orderedIds` is the DFS walk of the leaves, `start`/`end` bound each group's own
  subtree contiguously, and every group's slots follow the order the last full `group()` was
  handed
- **piles** — off in sha1Mode: nothing in `pileIndex`; on: one layout per non-empty leaf, its
  `order` a permutation of the leaf's slots, well-formed `bounds`, one sha1 per run
- **clusters** — I1 (every image of a bucket in exactly one pile), I2, I3 (`owned` agrees with
  the owner array), a leftover wherever a level was split, and a dead node resolvable through
  neither `nodeOf` nor the tree index
- **DEV invariants** — `import.meta.env.DEV` is on and `console.error` is captured, so any
  `[ClusterOverlay] I1..I5` report fails the step that provoked it
- **iterators** — the `nextImages` walk visits every image exactly once in `orderedIds` order
  and each position reports its own `getImageOrder()`; `prevImages` retraces it; the
  closed-aware walk shows exactly what an open path leads to; `collectRange` between two
  positions is the slice between them
- **selection** — the mask holds nothing but real slots
