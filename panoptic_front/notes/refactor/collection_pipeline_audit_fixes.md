# Collection pipeline — audit fixes

What an audit of `CollectionManager` → `FilterManager`/`SortManager`/`GroupManager` →
`GroupResult`/`GroupNavigator`/`ClusterManager`/`groupOps` turned up, and what was changed.
Architecture context: `collection_inspection_mission.md` (the split of engine / result /
navigator / clusters) and `cluster_view_goals.md` (the queue-drain model the group view
is built on).

The split itself held up. What did not was its *adoption*: the facade was half-wired, one
extracted mechanism was inert, and the incremental (`updateSelection`) path had drifted out
of agreement with the full-rebuild (`group()`) path in several places.

Everything below is a fix already applied. **Historical record:** the cluster half was
rebuilt again after this audit, so the paragraphs that name `ClusterManager.reconcile`,
`reapplyAfter`, `attachCustomGroups` or a `customGroups` registry describe code that no
longer exists — they are annotated where that matters. `collection_inspection_mission.md`
§*What the cluster half actually is now* has the current structure. The *"Left open"* list
at the end is superseded by **Open work** in `README.md`.

---

## 1. The dirty-instance payload was the wrong type

`dataStore.triggerRefs` emitted `Array.from(dirtyInstances)`, but every listener is typed
against `Set<number>` — and `CollectionManager.setDirty` actually called `.delete()` on it.
On any tab with `filterBySelection` (i.e. every selection tab, see `TabManager` constructor)
that threw on the first data change.

Worse in principle: `EventEmitter.emit` hands **the same object** to every listener, so the
narrowing loop was mutating a payload shared with every other collection — collection #2 saw
the list collection #1 had already pruned.

**Fix.** `triggerRefs` emits `new Set(dirtyInstances)` — a copy, because the store clears its
own set immediately afterwards and listeners may retain the payload. `setDirty` narrows onto
a locally built set instead of mutating the argument.

## 2. Nested grouping accumulated stale and duplicated slots

`imageToGroups` only ever holds the **deepest** property level (`group()` fills it from
`_leafGroups`) plus clusters. `updateSelection` derived its dirty set exclusively from that
map, so with `groupBy.length >= 2` the *intermediate* groups were never marked dirty and
never had the changed slot removed — while `addInstanceToGroups` re-added it at **every**
level. An image whose first-level value changed stayed counted in its old first-level group,
and repeated edits piled duplicates into `slots`.

That array is not internal bookkeeping: counts, `groupSlots` (called `collectSlots` at the
time), the cluster cards' representative image and the map view all read it.

**Fix.** After collecting the dirty leaves, `updateSelection` walks `.parent` up from each and
marks the whole chain. Single-level and ungrouped collections are unaffected (their leaves'
only ancestor is the root, which was already dirty).

A welcome side effect: the empty bucket of a clustered view is now reliably dirty, so the
pile refill sees an accurate `parent.slots` and the queue-drain reflow of
`cluster_view_goals.md` D5 behaves as documented. *(That refill was
`ClusterManager.reconcile` when this was written; it is `ClusterOverlay.resyncDirty` now,
gated on the same dirty group ids — the reasoning is unchanged.)*

## 3. `updateSelection` could unregister the root

The sweep that drops emptied groups did `delete index[group.id]` without excluding id 0. When
a collection emptied, `result.root` kept pointing at the root object while `index[0]` was
gone: `hasResult()` still returned true, every iterator resolved to `undefined`, and no later
`updateSelection` could repopulate it (it looks the group up *through* the index). The tree
stayed broken until a full `group()`.

**Fix.** The root is never unregistered.

## 4. Deleting a tab leaked its whole pipeline

`tabStore.deleteTab` and `tabStore.clear` did `delete managers[id]` and nothing else;
`TabManager` had no teardown at all. Every dropped tab left N `CollectionManager`s holding a
live `dataStore.onChange` listener plus five config watches — still running filter → sort →
group on every data change, forever. `CollectionManager.dispose()` existed but was only
reachable from `pruneCollections`.

**Fix.** `TabManager.dispose()` disposes every collection it built; both store paths call it.
`CollectionManager.dispose()` additionally bumps `runToken`, so a run still awaiting a column
load bails instead of writing into a collection nobody references.

## 5. `group()` was never awaited

`group()` is async — it awaits `_ensureColumns()` before building. Every call site fired it
and moved on, clearing `runState.isDirty` on the next line. So `isDirty` went false (and
`TabManager.update()` resolved) before the tree existed, and any throw inside — e.g.
`computeSha1Piles` on a slot with no sha1 — became an unhandled rejection.

**Fix.** Awaited in `update()`, both `runReload` branches and `setDirty`, with the run token
re-checked afterwards so a superseded run can't publish. `updateInstances` keeps the promise
(`this.pending`) and logs failures instead of dropping them.

Related: the `'sortGroups'` branch of `runReload` was the only one that never cleared
`isDirty`, so changing a group sort option left the collection permanently marked dirty.

## 6. Assign-then-drain raced its own reflow

`GroupView.assignClusterValue` awaited `setPropertyValue` and then drained. But the value
write fires `onChange` → `setDirty`, which is *async* — so awaiting the write only guaranteed
the reflow had **started**. The drain landed in the middle of it, not after it as the comment
(and D5) describe.

**Fix.** New `CollectionManager.settle()` resolves once no data-driven reflow is in flight
(chained, not snapshotted, so a reflow started while awaiting an earlier one is covered).
`assignClusterValue` awaits it before draining.

## 7. Iterators lost their options after one hop

`GroupIterator.nextGroup`/`prevGroup` constructed successors with **no options**, so a walk
silently reverted to defaults after a single step. And `nextGroup` never consulted
`ignoreClosed` at all, while `prevGroup` always had — the flag worked backwards and not
forwards.

**Fix.** A `protected at(groupId)` helper carries `this.options` to every hop, and the forward
descent honours `ignoreClosed` symmetrically. No current caller passes the flag, so this is a
correctness fix with no behavioural change today.

## 8. `findImageIterator` fabricated an invalid iterator

On a miss it fell through with `idx = -1`; since `-1 ?? 0` keeps `-1`, the result was an
iterator whose `slot` was `undefined`. `TreeScroller` then "selected" it, writing a
non-numeric key onto the selection `Uint8Array`. It also dereferenced `index[groupId]`
unguarded.

**Fix.** Returns `undefined` when the group is gone or no longer holds the image. The one
caller already guarded.

## 9. Newly imported images sorted to the front of every group

`updateSelection`'s re-sort reads `_posArr`, built only by `group()`. Slots that appeared
since had no entry and fell back to `0` — i.e. *ahead of everything*, whatever the sort said.

**Fix.** `_posArr` is pre-filled with `-1` so "position 0" and "absent" are distinguishable,
and a new `slotPos()` gives absent slots `_posCount + slot` — after everything the last full
sort ordered, in arrival order.

## 10. Smaller correctness fixes

- **`verifyState` didn't backfill `options`.** `computePropertySubGroup` and `sortGroup`
  dereference `options[propId]` unconditionally, so a persisted `groupBy` written without
  going through `setGroupOption` crashed the whole build. Missing entries are now created.
- **`buildOrdinalRanges` under-allocated.** It sized `orderedIds` from `root.slots.length`,
  but under tag grouping one instance lands in several leaves, so the DFS emits more entries
  than the root holds — the overflow was silently dropped (out-of-range typed-array writes
  are no-ops), truncating the order and leaving out-of-range `start`/`end`. It now counts the
  leaves first.
- **`removeChildren` leaked grandchildren.** It unregistered only the direct children, so a
  deeper subtree stayed in `result.index` as unreachable orphans — still walked by every
  `objValues(index)` sweep and still resolvable by `getGroupIterator(id)`. It now detaches the
  whole subtree (index, `valueIndex`, `pileIndex`, `imageToGroups`).
- **`reapplyAfter` could destroy a property level.** It replayed clusters through
  `setChildGroup`, which *replaces* the parent's children — so re-grafting onto a group that
  had since gained property sub-groups would delete that level. Made leaf-only. This was
  previously masked only by `setGroupOption`/`delGroupOption` calling `clusters.clear()`.
  *(Obsolete: there is no replay. The same hazard is now handled by
  `ClusterOverlay.resync`, which detects `hasForeignChildren` — a bucket whose children are
  a property level rather than this container's piles — and leaves the tree alone, parking
  the container until the bucket is a leaf again.)*
- **Two disagreeing `subGroupType` rules.** `setChildGroup`/`addChildGroup` took
  `children[0].type`; `groupOps.refreshSubGroupType` required all children to agree. A mixed
  level could therefore be labelled `Property`, and `sortGroups` would then dereference
  `meta.propertyValues[0].propertyId` on a Cluster child. Both paths now use
  `refreshSubGroupType` (exported for the purpose).
- **`delCustomGroups` dereferenced a possibly-absent group**; the registry can outlive the
  tree node. It now drops the record and returns. *(Still true in spirit: a
  `ClusterContainer` outlives its bucket, and `delCustomGroups` resolves the container and
  returns when there is none.)*
- **`deactivate()` left a debounced reload armed**, so a timer set while visible still fired
  after the tab was hidden. Activation goes through a new `CollectionManager.setActive()`
  that cancels it.

---

## Performance

### `buildOrdinalRanges` is now lazy

It ran a full O(n) DFS on *every* structural edit — `group()`, `updateSelection`,
`moveImagesToGroup`, `split`, `merge`, `deleteGroup`, `delCustomGroups`, `addCustomGroups`,
`drain`, `setSha1Mode` — to produce `orderedIds` / `start` / `end`, which **nothing outside
`core/group/` reads**. A single drag in the group view paid a whole-collection sweep for it.

`buildOrdinalRanges()` now just sets `cacheStale`; `orderedIds` became a getter that
materialises on read via `ensureOrderedIds()` (also exposed on `IteratorHost`, since
`getImageOrder` reads `start`). The call sites are unchanged — the work moved, the API didn't.

### `applySha1Piles` can be scoped

It rebuilt the pile overlay for the entire tree on every edit. It takes an optional
`only?: Iterable<Group>` — but when this was written both `moveImagesToGroup` and `drain`
called it with **nothing**, so the claim that they "pass the two leaves they actually
touched" was false. It is real now, and the unit is not two leaves.

The scope is **`ClusterOverlay.containerGroups(c)`**: for each container the edit resynced,
the bucket itself plus **every group in its node table** — live, dead and detached. That is
the right set because a `resync` refills *all* of the container's piles from the authored
map, not just the two the caller named; and including the dead and detached nodes is what
makes the scoped pass *drop* their stale `pileIndex` entries instead of leaving them behind.

Every structural op passes it: `addCustomGroups`, `delCustomGroups`, `merge`, `deleteGroup`
and `ClusterManager.drain` pass `containerGroups(c)` for the container they touched;
`moveImagesToGroup` passes the union over both containers plus the named `from`/`to` groups
(either may be an ordinary group rather than a pile). `clearCustomGroups` deliberately
passes **nothing** — it drops every container, so a full rebuild of the overlay is the
correct scope.

Detached or no-longer-leaf groups have their entry dropped, so scoping stays self-healing.
With sha1Mode off it no longer reallocates the map for nothing.

**Still unscoped:** `updateSelection` calls `applySha1Piles()` with no argument, so the
incremental path still sweeps the whole tree once per update (see `README.md` §Open work).

### Other

- `reapplyAfter` used to pay a full `applySha1Piles` + `setOrder` **per re-grafted bucket**,
  immediately before `group()` did all of it once. A new attach-without-finalising helper
  split the two. *(The shape survives the rebuild under different names: `groupOps` has one
  `finalise(host, emit, touched)` — `applySha1Piles` + `setOrder` + `buildOrdinalRanges` +
  the optional emit — and `applyClusterGroups` does the attach without it, with
  `addCustomGroups` being that plus `finalise`. `attachCustomGroups` itself is gone.)*
- `CollectionManager.update()` writes slots straight into a pre-allocated `Int32Array`
  instead of a boxed `number[]` plus copy (it hands `FilterManager` an exactly-sized array,
  since `lastSlots` is retained).
- `nextImages`/`prevImages`/`collectRange` each cloned an iterator per step — one extra
  allocation per image on a walk that covers the whole dataset. The loops only ever read and
  reassign, so the clones are gone.
- The dead `keys` accumulator in `addInstanceToGroups` is removed; besides being unread, its
  `push(...spread)` could blow the stack on a wide tag fan-out.
- Leftover `console.time` pairs removed from `FilterManager.filter`, `SortManager.sort`,
  `GroupManager.group`, `TreeScroller.computeLines`, `GridScroller.computeLines`, plus a
  `console.log` in a `GraphView` computed. The `TreeScroller` one was unbalanced — an early
  `return` skipped its `timeEnd`, so it warned on every subsequent call.

---

## Facade

`CollectionManager` gained `openGroup` / `closeGroup` / `toggleGroup` / `sortGroups`, the
methods whose absence forced views to reach through `.groupManager` anyway. `GroupView` and
`TabManager.getSha1Mode` now go through the facade.

### The scrollers no longer take a `GroupManager`

They take a **`GroupInspector`** (`core/group/inspector.ts`) — the read + view-state surface
they actually render against: `result` / `version` / `groupState` / `selectionNamespace`,
the three iterator getters, open/close + `emitResult`, the selection toggles, and the four
cluster/custom-group ops reachable from a group line. Deliberately *not* in it: filter, sort
and group configuration, or any rebuild entrypoint — what a scroller must not do is absent
from its type.

`GroupManager` and `CollectionManager` both `implements GroupInspector` (the latter by
delegation, as it already did). So `ViewPanel` / `MainView` / `GroupView` now pass
`collection` straight in, while the panels with no collection behind them — `ImagePreview`,
`RecoPanel` / `RecommendView`, the `Instances` modal — keep passing their standalone
`GroupManager`. Both work through the same prop, with no `.groupManager` reach-through at
the call site.

Mechanics: `TreeScroller`/`ClusterScroller`'s `groupManager` prop is renamed `manager`,
matching `GridScroller`; `GroupManager` gained a `groupState` getter (alias of `state` —
`CollectionManager.state` is the CollectionState, so the shared surface needed the other
name) and `CollectionManager` an `emitResult()`. `GridScroller` moved from runtime
(constructor-based) `defineProps` to a type declaration, since an interface has no runtime
constructor to name; that un-masked three pre-existing `ScrollerLine` shape errors in that
file, left as they were.

Still typed against `GroupManager`: `GroupForm` (`ContentFilter`, `FilterPanel`) and
`RecoPanel`'s own prop — grouping *configuration*, not inspection.

---

## Left open — these need a decision (superseded)

> **Superseded.** Kept as the record of what this audit left behind. The current list is
> **Open work** in `README.md`. Item by item: iterator invalidation was **deleted**, not
> wired; all four "dead API" entries are **gone** from the group system; the other three
> are still open and restated in the README.

- **Iterator invalidation is inert.** `GroupIterator` only registers itself when
  `options.register` is true, and nothing ever passes it — so `invalidateIterators()`, called
  from about ten places, always iterates an empty array and `isValid` is never flipped by a
  rebuild. The problem it was designed for is live: `TreeScroller.reconcileLines` reuses line
  objects when slots match, keeping `ImageIterator`s that hold `Group` objects detached from
  the rebuilt tree. Either wire `register: true` into the scroller-owned iterators or delete
  the mechanism — wiring it changes stale-iterator behaviour in the scrollers.
- **Dead API to prune or keep**: `propagateSelect`/`propagateUnselect` and `Group.view.selected`
  (no readers outside core), the `onlyPropertyGroups` iterator option (declared, never used),
  `CollectionState.instances` (never assigned).
- **`collection.delete(groupId)`** reads like it deletes the collection.
- **`filterBySelection` semantics**: `setDirty` drops non-selected instances from the dirty
  set entirely, so an image that gets *deselected* lingers in the collection instead of being
  filtered out. Existing behaviour was preserved deliberately — changing it is a product call.
- **Whole-dataset line construction**: `TreeScroller` builds an `ImageIterator` per image and
  `GridScroller` a line object per image, for the entire collection, on every version bump.
  Both are virtualised only *after* that. See `tree_scroller_computelines_optimization.md`.

---

Also worth knowing, found after this audit and not fixed here: `orderSlots` still walks the
whole of a dirty group's slot array to *check* that it is ordered even when nothing was
appended, which for the root is the whole collection once per update. And
`ImageIterator.fromGroupIterator` reads `it.group.id` before constructing, so an invalid
source iterator throws instead of returning `undefined`. Both are in `README.md` §Open work.
