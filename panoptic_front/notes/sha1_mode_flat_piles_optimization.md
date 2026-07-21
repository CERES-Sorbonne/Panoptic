# sha1Mode: flatten piles instead of materializing Groups

## How sha1Mode is managed today

`GroupManager.state.sha1Mode` is a boolean. When it's on, after the property/cluster
tree is built, `groupLeafsBySha1()` (`GroupManager.ts:589`) walks every leaf group
(`children.length === 0`) and calls `groupBySha1()` on it. That function
(`GroupManager.ts:669`) creates **one real `Group` object per unique sha1**:

- allocated via `buildGroup` (full object: `key`, `children[]`, `meta`, `view`,
  `start/end`, …),
- given a stable id from `valueIndex.get([...group.key, sha1])` — which grows the
  persistent `Map`-of-`Map`s tree by one branch per sha1,
- registered in `result.index`,
- attached as a `GroupType.Sha1` child, with the parent's `subGroupType` set to `Sha1`.

`buildOrdinalRanges` (`:438`) then special-cases `subGroupType === Sha1`: it does *not*
recurse; it flattens each child's slots straight into `orderedIds`. So the sha1 children
exist **only** to be an index-addressable list of piles. Everything downstream reflects
that:

- `ImageIterator.getSlots()` (`:1392`) returns `group.children[imageIdx].slots`;
  navigation length is `group.children.length`.
- `TreeScroller.vue:174` and `GridScroller.vue:158,193` branch on
  `subGroupType === Sha1` and render one pile line per child, keyed off the child's
  `id` and first slot.
- `updateSelection`, `moveImagesToGroup`, `addCustomGroups`, `setAsRoot` all tear down
  and rebuild these children on every mutation (`removeSha1Groups` → `groupBySha1`).

### The cost

Since most images have a unique sha1 (pile size 1), sha1Mode materializes on the order
of **one Group + one `index` entry + one `valueIndex` branch per image**, and
re-materializes them on every incremental update. sha1 groups are deliberately kept out
of `imageToGroups` (`setChildGroup:1016`, `addChildGroup:1027`), so that map is
unaffected — the blow-up is `result.index` and `valueIndex` (the latter also leaks: sha1
branches accumulate in the persistent value tree).

## The optimization: flat slots + run boundaries

Keep slots flat with equal-sha1 runs contiguous, and record run boundaries instead of
child Groups. The sha1 children carry **no information that a `(offset, length)` run
doesn't** — they're a display-only partition, never in `imageToGroups`, never recursed
into.

Per leaf group, store two arrays instead of `n` child Groups:

```ts
group.pileSlots?: number[]   // slots reordered so equal-sha1 are contiguous
group.pileBounds?: number[]  // cumulative offsets, length = numPiles + 1
```

Build them with a stable bucket pass (sha1 → bucket, emit buckets in first-seen order) —
this reproduces today's ordering exactly (first-appearance order of sha1, slot order
within a pile). Pile `i` is `pileSlots.slice(pileBounds[i], pileBounds[i+1])`; pile count
is `pileBounds.length - 1`.

Keep `group.slots` in display order and store the piled arrays separately, so toggling
sha1Mode off is non-destructive.

### Wins

- **Zero Group / `index` / `valueIndex` growth** from sha1 — the biggest win; also
  removes the valueIndex leak.
- `removeSha1Groups` and the rebuild-on-mutation paths become "recompute two arrays,"
  not "delete N Groups from three structures and re-insert."
- Toggling gets cheap enough that pile bounds could be computed always, letting the
  scroller decide whether to render piled — no structural rebuild at all.
- The tree/grid `subGroupType != Sha1` guards *simplify*: a piled leaf stays a genuine
  leaf (`children.length === 0`), so "has real subgroups" becomes just
  `children.length > 0`. Add one `group.sha1Piled` flag to switch pile rendering on.

## Touch points to convert

1. **`groupBySha1` / `groupLeafsBySha1`** → compute `pileSlots`/`pileBounds` per leaf
   instead of building children.
2. **`buildOrdinalRanges`** → the `Sha1` branch reads `pileBounds` to set per-pile
   `start` (or emit `pileSlots` in order; per-pile starts derive from bounds).
3. **`ImageIterator`** (`getSlots`, `getSha1Group`, `nextImages/prevImages`,
   `getImageOrder`, `findImageIterator`) → index into piles via bounds instead of
   `group.children[imageIdx]`. `sha1Group.slots` becomes the slice.
4. **Scrollers** (`TreeScroller`, `GridScroller`, `Image.vue` count badge,
   `RowLine.vue`) → iterate `numPiles` and slice; render key from first instance id
   (they already derive keys from `firstId`, so `sha1Group.id` isn't essential).
5. **`updateSelection` / `moveImagesToGroup` / `addCustomGroups` / `setAsRoot`** →
   recompute bounds instead of remove+rebuild children.

## Decide before implementing

- **Slots with no sha1 are currently dropped** — `groupBySha1:677` does
  `if (!sha1) continue`, so in sha1Mode those instances vanish from the view. Replicate
  (skip from `pileSlots`) or fix (emit as singleton piles). Confirm which is intended;
  the rewrite is a natural moment to make it explicit rather than an accident of the loop.
- **Cluster / `isSha1Group` groups** (`utils.ts:378`, `allChildrenSha1Groups`) come from
  the backend as sha1-based clusters — a separate concept from display piling. Ensure the
  new pile flag doesn't collide with `isSha1Group` semantics.

## Bottom line

The instinct is correct and the payoff is large: it removes the per-image
Group/index/valueIndex allocation that is the entire cost of the feature. The work is
mechanical but spread across the iterator and both scrollers, since they currently lean
on `group.children[i]` as the pile handle — that's the one abstraction being replaced
with `(pileSlots, pileBounds)`.

---

# sha1 as the final compose overlay (with clusters)

See `collection_inspection_mission.md`. That mission defines the pipeline

```
propertyTree + clusterRegistry (+ sha1Mode) → GroupResult
```

and explicitly notes (§2) that sha1 grouping is *already* a display overlay done the
same messy inline way as clusters, so it should get the same home. The flat-piles model
above is what makes that clean: sha1 stops being tree structure and becomes a pure
annotation, so it can run **last**, over whatever leaves the composed tree ends up with.

## Where sha1 sits in the pipeline

```
1. build propertyTree            (GroupManager engine, no cluster/sha1 knowledge)
2. apply clusterRegistry overlay (cluster groups replace children of their parent)
3. apply sha1 pile overlay       ← NEW final pass: annotate every leaf with piles
4. buildOrdinalRanges + iterators (GroupResult)
```

Step 3 is a single sweep over the composed tree's **final leaves** (`children.length === 0`)
that computes `pileSlots`/`pileBounds` per leaf. It doesn't care whether a leaf came from
a property or a cluster — a cluster group *is* a leaf (holds slots, no children), so the
same sweep piles inside cluster groups too.

## Why this is strictly simpler than today

- Today `groupLeafsBySha1()` runs against property leaves, and then
  `addCustomGroups` has to **re-apply** `groupBySha1` to cluster children
  (`GroupManager.ts:828`) because clusters are grafted in *after* the sha1 pass. Ordering
  the pipeline so clusters compose first and sha1 piles last **deletes that special-case**
  — one leaf sweep covers property leaves and cluster leaves uniformly.
- `removeSha1Groups` disappears. The overlay is non-destructive (it never mutates
  `slots`, `index`, or `valueIndex`), so toggling sha1Mode or recomposing is just
  "clear pile annotations, recompute" — no tree rebuild, no group deletion.
- Cluster special-cases in `updateSelection` shrink: property updates never touch pile
  data, and pile data is recomputed on recompose anyway.

## Where to store the pile data — prefer a side map on GroupResult

Two options:

- **On the Group node** (`group.pileSlots`, `group.pileBounds`, `group.sha1Piled`) —
  simplest to read, but mutates shared tree nodes on every sha1 toggle.
- **Side map on GroupResult** (`Map<leafGroupId, { pileSlots, pileBounds }>`) — keeps
  Group nodes pure display-agnostic data, which matches the mission's "separate sources
  of truth" ethos. Toggling sha1Mode rebuilds only this map; the property/cluster tree is
  untouched. Iterators/scrollers do one map lookup by leaf id (they already hold the
  `GroupResult`/manager).

Recommend the **side map**: it makes sha1 a genuine overlay owned by `GroupResult`
alongside `imageToGroups`/`orderedIds`, and means recompose = drop the map + one sweep.
`buildOrdinalRanges`' `Sha1` branch then keys off "does this leaf have a pile entry"
instead of `subGroupType === Sha1`.

## Interaction to nail down: display piling vs `isSha1Group` clusters

These are orthogonal and must not be conflated:

- **`isSha1Group` cluster** (`utils.ts:378,403`): the *backend* clustered by sha1, i.e.
  it decided which cluster an instance belongs to. Structural, lives in the registry.
- **sha1 pile overlay**: collapses duplicate-sha1 *instances within a single leaf* for
  display. Cosmetic, lives in the overlay.

The pile sweep runs the same way regardless of whether a leaf is an `isSha1Group` cluster
— it just piles identical sha1s inside it. Keep the `sha1Piled` flag (or side-map key)
distinct from `isSha1Group` so the two never collide.

## Net

Reordering the pipeline to `clusters → sha1 (last)` plus the flat-pile representation
turns sha1Mode into a ~single-function final pass with no structural footprint, and
removes the only place clusters and sha1 currently have to know about each other
(`addCustomGroups` re-piling cluster children).

---

# Implementation plan

## Representation (decided)

**No sub-groups.** A leaf's instances stay a flat array. sha1Mode is expressed as a
side structure the scrollers read; the scrollers own turning it into piles. GroupManager
never splits a leaf into child Groups for sha1.

Per piled leaf, store:

```ts
interface PileData {
    order: number[]    // the leaf's slots, pile-ordered (equal-sha1 contiguous), singleton nulls
    bounds: number[]   // first-index of each pile; append order.length as final sentinel
}
```

- Pile count = `bounds.length - 1`. Pile `k` = `order[bounds[k] .. bounds[k+1]]` — the
  scroller reads pile 3 as `order[bounds[3]]…order[bounds[4]]` with **no sha1 comparison**.
  This is the "index of each first sha1" array requested — the perf point is precomputing
  boundaries so the scroller never scans sha1 strings.
- **null-sha1 slots must throw.** A null sha1 is never valid (sha1 is written eagerly at
  instance creation), so the pile pass throws rather than dropping or piling it — surfaces
  the real cause instead of hiding it. Replaces today's silent `if (!sha1) continue`. See
  Q1 resolution below.
- **A flag on the result object** tells scrollers to render piled (`result.sha1Mode` already
  exists on state; expose per-leaf presence in the pile map as the "this leaf is piled"
  signal).

### Canonical slots vs pile order

Keep `group.slots` in pure sort order (unchanged, non-destructive). `PileData.order` is a
**separate** pile-ordered permutation, allocated only when sha1Mode is on.

**Every non-empty leaf gets an entry when sha1Mode is on** (not only leaves with
duplicates). An all-unique leaf still gets a trivial layout (`order === slots`, `bounds
=== [0..n]`). This matters: the tree/grid render *piled* leaves through a different path
than *flat* leaves — the pile path uses `pileLineSizeFor` + sha1-mode properties, the flat
path uses `imageLineSizeFor` + all properties. If all-unique leaves fell back to the flat
path, sha1Mode would mix two row-height regimes (overflow bug). Uniform piling matches the
old behaviour exactly. Cost is still just two plain number arrays per leaf — no Groups, no
`index`/`valueIndex` entries — so the perf win stands.

Store in a side map keyed by leaf group id. Pre-cluster-mission it lives on the group tree
(`result.pileIndex: Map<groupId, PileData>`); post-mission it moves to `GroupResult` next
to `imageToGroups`/`orderedIds`.

Nothing else is allocated: no `index` entries, no `valueIndex` branches, no child Groups.

### Pipeline order (decided, Q2)

`group()` and custom-group insert/update produce the flat property+cluster tree; **applying
sha1Mode is the final step of each of those entry points**:

```
group():                 build property tree → (replay custom groups) → applySha1Piles
addCustomGroups/update:   mutate tree → applySha1Piles
```

`applySha1Piles` = clear `pileIndex`, then one sweep over final leaves computing `PileData`.
No structural rebuild; toggling sha1Mode re-runs only this pass.

## Iterator depends on `GroupResult`, not `GroupManager`

The iterator touches `this.manager` in only three ways: `registerIterator` (invalidation),
threading the reference into child iterators, and `this.manager.result.index[...]` for data.
Everything it *reads* is already `result`. So:

- `GroupIterator`/`ImageIterator` take a **`GroupResult`** and become pure readers over
  `{ index, pileIndex, orderedIds }`. `getGroup()` → `result.index[id]`;
  `getImageOrder()` → `group.start + bounds[imageIdx]` from `result.pileIndex`.
- Move the `iterators[]` registry + `isValid` invalidation onto `GroupResult` (iterators
  are invalidated exactly when the result is rebuilt). This is the only non-data manager
  dependency.
- The pile design reinforces this: piling is *data* in `result.pileIndex`, not behavior on
  the manager, so the iterator reads piles with no manager call.

Matches cluster mission §2 (extract `index`/`imageToGroups`/`orderedIds`/iterators/version
into the result object).

## Reverting sha1Mode — the cluster is recovered for free

Because piling is a **non-destructive side map**, applying sha1 never mutates a cluster's
`slots`, `children`, `index` entry, or order — it only writes a `pileIndex` entry keyed by
the group id. Therefore:

- **Revert = `pileIndex.clear()` + rebuild `orderedIds` from the untouched tree.** The
  cluster is already whole; there is nothing to reconstruct.
- The cluster's canonical instance order (e.g. by score) lives in `group.slots`;
  `pileIndex.order` is a separate permutation used only while sha1Mode is on. Toggle off →
  scrollers read `group.slots` again.
- Post-mission, reverting is even cleaner: re-run compose from
  `propertyTree + clusterRegistry` and skip the sha1 pass — the cluster comes straight from
  the registry.

This is the decisive reason to keep pile data in a side map rather than on the Group node:
the old `groupBySha1` **replaces** `children` with sha1 subgroups (and `addCustomGroups:828`
re-piles cluster children in place), which is destructive to structure and forces a rebuild
to revert. The side map makes revert a clear-and-recompute.

## File ownership (concern → file)

The core separation: **the pile algorithm is a pure function**, storage is a field on the
result, wiring/reading stays in the manager, rendering stays in the scrollers.

| Concern | File (Phase 1, today) | File (Phase 2, after GroupResult extraction) |
| --- | --- | --- |
| `PileData` type | `src/core/sha1Piles.ts` (new) | same |
| **Pile algorithm** — `computeSha1Piles(slots, sha1s) → PileData`; stable-bucket by sha1, singleton runs, `bounds` with sentinel, **throw on null sha1**. Pure, no store/tree knowledge, unit-testable. | `src/core/sha1Piles.ts` (new) | same |
| Pile storage — `pileIndex: Map<groupId, PileData>` | `GroupManager.result` (`GroupTree`, `GroupManager.ts`) | `GroupResult` next to `imageToGroups`/`orderedIds` |
| Pipeline wiring — `applySha1Piles()` final pass; called at tail of `group()`, `addCustomGroups`, `updateSelection`; toggle in `setSha1Mode` | `GroupManager.ts` | `GroupResult`/compose step |
| `orderedIds` — emit `PileData.order` for piled leaves | `GroupManager.buildOrdinalRanges` | `GroupResult` |
| Iterator — read piles via `bounds` (not `children`) | `ImageIterator` in `GroupManager.ts` | moves with iterators to `GroupResult` |
| sha1Mode flag/state | `GroupState.sha1Mode` (`GroupManager.ts` / `src/data/models.ts`) | unchanged |
| sha1 reads (`sha1s()`, `systemProps.SHA1`) | `src/data/columnStore.ts` (exists, no change) | unchanged |
| **Render** piles from `order`/`bounds` | tree: `TreeScroller.vue`, `Image.vue`, `GroupLine.vue`; grid: `GridScroller.vue`, `RowLine.vue` | unchanged |
| Backend `isSha1Group` cluster flag — **stays separate** | `src/utils/utils.ts` (`convert*GroupResult`, `allChildrenSha1Groups`) | unchanged |

Deleted, not relocated: `groupBySha1`, `groupLeafsBySha1`, `removeSha1Groups`,
`GroupType.Sha1` (structural use), and the `addCustomGroups:828` cluster re-pile.

## Phase 1 — flat piles, behavior-preserving (independent of cluster mission)

This lands the memory/perf win on the current architecture. Sequence it first; it can
ship before the cluster-separation mission.

1. **Add `PileData` + `result.pileIndex`.** New `computeSha1Piles(group)` on GroupManager:
   stable-bucket the leaf's slots by sha1 (sha1 → bucket array, emit buckets in first-seen
   order), write `{slots, bounds}` into `pileIndex`, set `group.sha1Piled`. Replaces
   `groupBySha1` (`:669`).
2. **`groupLeafsBySha1`** (`:589`) → iterate leaves, call `computeSha1Piles`.
   **`removeSha1Groups`** (`:597`) → clear `pileIndex` + `sha1Piled` flags (no index/tree
   surgery).
3. **`buildOrdinalRanges`** (`:428`) → for a piled leaf, emit `pileData.slots` (already
   pile-ordered) into `orderedIds`. Per-pile `start` is derived (`group.start + bounds[i]`),
   not stored on child groups.
4. **`ImageIterator`** — the central change. `imageIdx` becomes the pile index for piled
   leaves:
   - `getSlots()` (`:1392`) → `slots.slice(bounds[i], bounds[i+1])`.
   - drop `sha1Group: Group`; callers use the iterator's own `.slots` (already the pile).
   - `nextImages`/`prevImages` (`:1434`,`:1453`) → bound with `bounds.length - 1` instead
     of `children.length`.
   - `getImageOrder()` (`:1493`) → `group.start + bounds[imageIdx]`.
   - `findImageIterator` (`:988`) → find pile index by matching target sha1 against pile
     firsts.
5. **GridScroller** (`:193`) → loop `numPiles` from bounds; `PileRowLine.data` carries a
   pile handle `{ groupId, pileIndex, slots }` instead of a child `Group`.
   **RowLine** (`:173`) modal → `getImageIterator(pileHandle.groupId, pileHandle.pileIndex)`.
6. **TreeScroller** — already fully iterator-driven; the `subGroupType != Sha1` guards
   (`:170`,`:174`) become "is this leaf piled". `computeImagePileLines` (`:306`) is
   unchanged (it walks `ImageIterator.nextImages`).
7. **Image.vue** count badge (`:109`) → `props.image.slots.length` (the ImageIterator
   already exposes `.slots`).
8. **GroupLine.vue** (`:48`,`:151`,`:169`) → the `children.length > 0 && subGroupType != Sha1`
   checks collapse to just `children.length > 0`, since a piled leaf is now a genuine leaf.
9. **Mutation paths** — swap `removeSha1Groups`/`groupBySha1` for clear+recompute piles:
   `updateSelection` (`:705`,`:783`), `moveImagesToGroup` (`:871`), `addCustomGroups`
   cluster-child re-pile (`:828`), `setAsRoot` (`:636`), `delCustomGroups` (`:894`),
   `rootedAt` (`:961` — treat a piled leaf as a leaf).
10. **Retire `GroupType.Sha1`** as a structural type once no code reads it. Keep
    `isSha1Group` (backend cluster flag) — unrelated, see below.

Verify: tree + grid render identical piles/counts, sha1 toggle, shift-select across piles,
image modal from a pile, cluster + sha1Mode together, incremental update while sha1 on.

## Phase 2 — sha1 as the final compose overlay (rides the cluster mission)

Once `collection_inspection_mission.md` lands its compose step:

1. Move `pileIndex` onto `GroupResult`.
2. Make pile computation the **last** compose pass — a single sweep over final leaves
   after clusters are applied.
3. Delete the `addCustomGroups` cluster re-pile special-case (step 9 above): clusters
   compose first, one leaf sweep piles property leaves and cluster leaves uniformly.
4. sha1Mode toggle = re-run the final pass only; no property/cluster tree rebuild.

## Resolved

- **Q1 — null-sha1 slots → throw.** A slot is one instance occurrence; sha1 groups
  instances of identical file content. sha1 is written eagerly at instance creation
  (`columnStore.ts:186`), so a null sha1 is never valid — it signals a real bug (backend
  sent no hash, or a load-order fault). The pile pass throws so the cause is visible,
  replacing today's silent `if (!sha1) continue` (`groupBySha1:677`) which hid it.
- **Q2 — pipeline order** = `group → insert/update custom groups → apply sha1Mode`. sha1
  is the final pass of `group()` and of custom-group insert/update. Recorded above.
- **Q3/4/5 — representation** = flat instance array + first-index boundary array + a flag;
  no sub-groups; scrollers own rendering piles. Recorded above. Piling applies to *all*
  final leaves (property leaves and cluster leaves alike). Keep the pile structure fully
  separate from the backend `isSha1Group` cluster flag — orthogonal concepts.

## Still open

- **Cluster-leaf piling confirmation.** The "all final leaves" decision means cluster
  groups get piled too (matches today's `addCustomGroups:828`). Confirm no cluster view
  wants raw un-piled instances even when global sha1Mode is on.
- **Toggle-off cost.** With `order`/`bounds` in a side map, turning sha1Mode off is a map
  clear + `orderedIds` rebuild from `group.slots`. Confirm that's acceptable vs caching
  both orderings (it should be — one O(n) sweep).
- **Scroller-side details deferred** (per your note): render-key stability and any
  persisted pile view-state are non-issues for the data model; revisit when wiring the
  scrollers.
