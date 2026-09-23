# Cluster View — goals and functionalities

Definitive design note for the cluster view — its goals and the settled choices.
Architecture context: `collection_inspection_mission.md` (clusters as a source of
truth separate from the property tree).

**How to read this.** The paradigm, the goals, the invariants and the performance
decision are settled and still govern the code. Several *mechanisms* named here were
designed but never built; each of those is marked **Not built yet**. The design stays —
it is still the intent — but do not read a marked paragraph as a description of
`src/`. Current structure: `collection_inspection_mission.md` §*What the cluster half
actually is now*.

The cluster view is not a consultation view — it is a **tool for producing and
fixing property values**. Clustering is scaffolding; the durable output is the
property values written onto the instances.

## Core paradigm — the target *is* the leaf grouping property

The single organising idea, from which everything below falls out:

**Assigning is grouping.** The property you assign (the *target*) is always the
**leaf (deepest) grouping property** of the view — never a free-floating second
axis. There is one selector, not two: choosing "work on property `C`" *is*
grouping by `C`.

Consequences, by construction:

- **The target can be chosen late.** The leaf grouping level is the target; with no
  grouping there is no target *yet*. The view still works without one: the collection
  is one card (the root), which can be clustered, and its piles opened and dragged
  between (membership only — there is no value to write). Picking the target — from
  a card's **"Assign to…"** row or the inspector header, an existing property or a
  new one — is the act of *grouping by it*, which materialises the buckets below.
  **Adding a leaf level moves the clusters down instead of clearing them**: each
  clustered bucket's piles follow its undecided images into the new level's `empty`
  child, with the same pile ids (see *Grouping change* below). So a user can cluster
  first — the best way to see what the clusters are — and name the property after.
- **Every group is real.** A leaf group is either a **value-group** of the target
  (homogeneous, reproducible from data, persistable) or the **`empty` bucket**
  (the undecided images — those with no target value yet).
- **There is no `mixed`.** Grouping splits by value *by construction*, so a group
  never holds several target values. The only non-value state is `empty`
  (undecided), which is honest work-to-do, not ambiguity.
- **Clustering happens inside `empty`.** You cluster the undecided images so you
  can give a whole visually-coherent pile one value at once (G1).
- **Assigning drains the queue.** Assigning a cluster writes the target value onto
  its images; they leave `empty` and join their value-group. The finished pile
  moves out of the way — a predictable *queue-drain* reflow, caused by your own
  action (see G4).

## Goals

- **G1 — Assign property values fast, in bulk.** The end goal is to group / filter
  / sort images by value, but the values have to exist first, and setting them one
  image at a time is slow. Group by the target, cluster the `empty` bucket into
  visually similar piles, then give a value to a whole pile at once.
- **G2 — Correct an existing grouping.** Move mis-valued images between
  value-groups (inspectors + drag-and-drop) to fix wrong values. Clustering makes
  outliers stand out visually (a dog among cats), which the flat main tree hides.
- **G3 — Focus on one level.** Show the leaf grouping level only — the
  value-groups and the clusters of the `empty` bucket, side by side as peers, no
  depth or parent indication. Avoids the "close 1000 groups to see one" problem of
  the full tree, and stays cheap at ~1M images.
- **G4 — Stable while working.** The unworked piles must not jump around under the
  user. The only motion is the pile you *just assigned* draining out of `empty`
  into its value-group — predictable, self-caused, and desirable (progress
  feedback). Value-groups and unworked clusters keep their positions. A write to a
  property that is *not* the target (i.e. not the leaf grouping) changes nothing.

## Display model

The view renders the **leaf grouping level as a flat list of peer groups**:

- the target's **value-groups** (`cat`, `dog`, …) — real, homogeneous,
  persistable; and
- the **clusters of the `empty` bucket** (`cluster 1`, `cluster 2`, … + a leftover
  pile of un-clustered undecided images).

Both kinds sit at the same level; the `empty` container itself is implicit. A
cluster is a working pile of undecided images. **Assigning a cluster a value
promotes it into a value-group** (or merges it into the existing one). This keeps
G3's one-level rule: there is no visible parent/child depth, only peers, some of
which carry a value and some of which are still undecided.

## Example scenarios and how they're solved

### Scenario 1 — Label an unclustered collection with a new property (G1)

No values exist yet for `Animal`. You want to tag each pile `cat / dog / bird`.

- **Group by `Animal`** (this *is* picking the target). Everything lands in the
  `empty` bucket — nothing has an `Animal` value yet.
- **Cluster the `empty` bucket**. The undecided images split into visually similar
  piles, shown as peers.
- **Assign each cluster** its value. The write drains that cluster out of `empty`
  into the `cat` / `dog` / `bird` value-group. The pile you finished leaves; the
  rest stay put. Repeat until `empty` is drained.

### Scenario 2 — Fix a grouping that already exists (G2)

Already grouped by `Animal`; some images have the wrong value (a dog valued
`cat`).

- The value-groups `cat` and `dog` are visible (open two **inspectors** if
  needed). No `empty` work — the grouping is complete.
- Spot the outlier — it stands out among its neighbours — and **drag** it from
  `cat` to `dog`. Dropping into the `dog` value-group rewrites its `Animal` value
  to `dog`; it visibly moves. The correction *is* the drag.

### Scenario 3 — One clustering, several different attributes (G1)

Clustering is unsupervised, so different piles in `empty` are homogeneous on
*different* properties: one is all black-and-white (`ColorMode`), another all
portraits (`ShotType`).

- Solved by **sequential passes**, one target at a time (D2). Group by
  `ColorMode`, cluster its `empty`, sweep and assign the piles that are about it;
  then **change the grouping to `ShotType`** and sweep again.
- Changing the target (= changing the leaf grouping) **rebuilds the view** around
  the new property: new value-groups, a fresh `empty` bucket to cluster. Each pass
  starts clean.
- Re-clustering *within a pass* (the `empty` bucket) is always available and
  re-splits only the undecided images.

### Scenario 1b — Cluster first, choose the property after (G1)

No grouping at all. You don't know yet what the piles are about.

- **Cluster the root card.** Open piles in the two inspectors, drag images between
  them to fix the membership (no value is written: there is no target).
- On a pile's **"Assign to…"** row, pick a property — or **New property…** (the
  app's property modal, tag by default). The view groups by it; the piles move into
  its `empty` bucket with the same ids, minus the images that already had a value
  (those go to their value-groups). The row turns into that property's input.
- **Assign each pile** as in Scenario 1.

### Scenario 4 — A second, finer property under the first (G1)

Grouped by `Animal`; now you want a `Breed` under `cat`.

- Use **nested grouping**: `Animal → Breed`. The leaf — hence the target — is now
  `Breed`. Inside `Animal = cat` you get the existing breeds plus a `Breed`-`empty`
  bucket. Piles already made in `Animal = cat` (or in `Animal`'s `empty`) move down
  into that bucket's `Breed`-`empty` child instead of being lost.
- Cluster that `empty`, assign per pile. The `Animal` value above is untouched —
  you are only ever writing the leaf. Hierarchies are expressed as nested grouping,
  not as a target detached from the grouping.

### Scenario 5 — Several labels on the same image at once (G1)

You want an image to carry "beach", "sunset" and "crowd" simultaneously.

- Use **one tag-type target** holding multiple values; group by it. A value-group
  is then "images whose tag-set is exactly this," and `empty` is "no tags yet."
- We do **not** solve this with multiple targets at once (D2).

### Scenario 6 — Send an image back to the undecided pile

You assigned an image but want to reconsider it.

- **Drag it from its value-group into a cluster in `empty`** (or the leftover
  `empty` pile). Crossing back into `empty` **clears** the target value — the image
  is undecided again and rejoins the working queue. This is the inverse of
  assignment, and it falls out of the same "membership follows value" rule (D4).

> **Partly built.** Dragging works only **between the two inspector panes** on the
> right of the group view (`GroupView.onPaneAdd` → `moveImagesToGroup` + a write of
> the destination group's value, or a clear when the destination has none). The
> **cluster card grid is not a drop target** — `ClusterScroller` / `ClusterLine` have
> no draggable — so an image can only be sent back to a pile that is currently open in
> a pane. The same limitation applies to D4 below.

## Design invariants that make the scenarios work

- **D1 — Membership follows value; clusters subdivide only the undecided.** A leaf
  group's membership is *derived* from the target value (that is what grouping
  means). The only manual, structural subdivision is **clustering inside the
  `empty` bucket** — a convenience for bulk-assigning the undecided. Clusters carry
  no value of their own; they partition the `null`-valued region so you can give a
  pile one value at once.

- **D2 — One target at a time.** The target is the single leaf grouping property.
  No simultaneous multi-property assignment: it would force variable-height cards,
  and at ~1M images the virtual scroller needs line heights known **without
  measuring** — fixed-size cards are structural, not aesthetic. Multiple properties
  → sequential passes (Scenario 3); multiple simultaneous labels → tag-type target
  (Scenario 5).

- **D3 — A grouping *is* an assigned property, so assigning is grouping.** This is
  the whole paradigm. `empty` vs. a value is a group's *decidedness* on the target.
  There is no separate "homogeneity" state to compute — the grouping guarantees
  homogeneity. To work on a different property, change the grouping.

- **D4 — Drag writes the destination region's value.** Dropping an image sets its
  target value to the destination's:
  - into a **value-group** → writes that value (assignment or correction);
  - into a **cluster within `empty`** → sets the value to `null` (undecide), and
    the image joins that working pile;
  - between two clusters *within* `empty` → pure membership, no value change (both
    are `null`).

  > **Partly built — panes only.** All three rules are implemented, in
  > `GroupView.onPaneAdd`: it calls `moveImagesToGroup` and then writes the
  > destination group's shared value, clearing the property when the destination has
  > none (a cluster). But the only drop targets are the **two inspector panes**; the
  > cluster card grid is not draggable, so a drag is possible only between two piles
  > that happen to be open in panes.

- **D5 — Direct writes, queue-drain reflow (G4).** Assignment writes to the
  instances immediately — no pending state, no write button. Because the target is
  the leaf grouping, the write *does* reflow: the assigned images drain out of
  `empty` into their value-group. This is intended — only the pile you acted on
  moves, and it moves out of the way. Unworked piles and other value-groups are
  untouched. (This replaces the earlier "non-parent target → zero reflow" scheme:
  stability now comes from *only the acted-on pile moving*, not from nothing moving.)

## Persistence — clusters are ephemeral, values are durable

**A group survives a reload only if it is a value-group.** Value-groups are
reproducible from data (group-by the target reconstructs them), so they persist.
The **clusters inside `empty`** are an *on-the-moment* subdivision of the undecided
images — session-scoped scaffolding, **not persisted**; they vanish on reload
(reload leaves the still-undecided images in a fresh, unclustered `empty`).

To **save** a cluster, assign it a value — that drains it into a value-group,
which *is* reproducible and therefore durable. This is the whole thesis made
concrete: clusters are scaffolding, property values are the durable output.

Consequence: we don't engineer cluster membership to survive **undo** either.
**Undo applies to commits only** (committed property values / data). Cluster
structure is not on the undo log; if an undone commit changes a value, the view
recomputes its display from the current data (below) — e.g. an undone assignment
returns those images to `empty`, but not to their former cluster.

## Reactivity & sync

**Assumption:** no concurrent multi-user editing of the same images/property — by
convention users work on different images/properties. The realistic case is *we
ourselves* change a property in another view; we know when we do it, so the view
reflowing in response is expected, not a surprise.

Because clusters are ephemeral and only ever subdivide `empty`, the reaction is
minimal — `empty`-bucket maintenance only, never re-clustering:

| Change | Effect |
|---|---|
| **Sort** | display order only; re-`setOrder` over the tree |
| **Filter** | mask members that don't pass; the group/cluster nodes stay intact (reversible) |
| **Assign (target value change)** | the assigned images leave `empty` for their value-group (queue-drain); the drained slots drop out of their cluster. O(delta) via `drain` |
| **Value change on the target from elsewhere** | **Not built yet** as a dedicated mechanism — there is no `reconcile`. What exists is `ClusterOverlay.resyncDirty(dirtyGroupIds)`, called from `updateSelection`: it refills the piles of the buckets the edit touched, gated on the dirty group ids rather than on the target property. An image that gains a value leaves the bucket and so leaves its pile (with a `drained` record, so an undo returns it to that pile); one that loses it comes back and routes to the leftover unless a drain record says otherwise. Cost is O(\|bucket\|) per touched bucket, not O(\|updated\|) |
| **Explicit cluster edit** (cluster / drag / merge / delete inside `empty`) | the only thing that *structurally* mutates the cluster set |
| **Grouping change: a leaf level appended** (i.e. choose or refine the target) | **rebuild**, and the clusters **move down**: `setGroupOption` records a pending level (`ClusterManager.deferDescent`) instead of calling `clusters.clear()`; the rebuild's `resyncAll` re-keys each container to its bucket's `[...key, undefined]` child (`ClusterOverlay.descend`) before refilling. Pile ids are unchanged; images of the bucket that already have a value on the new level are released (drain records kept, so clearing the value brings them back); filtered-out members stay owned (masked). A bucket with no `empty` child left drops its container. A cluster run on the old bucket that returns afterwards fails with `not-a-leaf` |
| **Grouping change: a level removed or reordered** | **rebuild** — the images are regrouped, so `clusters.clear()` drops every container |

**Reset button.** *(Not built yet.)* Intended: always available to rebuild from the
current tree (clean slate) — re-derive the value-groups and re-cluster (or clear) the
`empty` bucket. Also the escape hatch for "I filtered to a subset specifically to
cluster it — rebuild for this filtered set" when the mask default isn't wanted.
There is no such control in `GroupView.vue`. The nearest things that exist are
per-group `delCustomGroups` (the card's "close clusters" ✕, and the tree view's) and
the collection-wide `clearCustomGroups`, which drops every container.

## Performance & data flow (~1M images) — grafted real groups, not a derived overlay

**Goal.** Rendering, scrolling, iteration and selection over ~1M images must be
cheap on the hot path, and cluster edits must be cheap on the cold path. The design
question was where the `empty` clusters *live*.

**Two options were considered:**

- **Derived overlay** — keep clusters as membership `Set`s in a side structure and
  *derive* the displayed lines every time (`deriveEmpty`: one O(|empty|) pass over
  the empty bucket's filtered+sorted slots, routing each slot to its cluster via a
  `slotToCluster` map, leftover falling out of the same pass). Clean and stateless,
  but every render / scroll / filter / sort re-pays O(|empty|), and the tree's own
  iterators/selection don't see the clusters, so those paths need a parallel code.

- **Grafted real groups** *(chosen)* — materialise each cluster as a real `Group`
  node grafted into the property tree under the `empty` bucket. Once grafted, the
  existing tree machinery renders, scrolls, iterates, orders and selects them for
  free — **O(0) on the hot path** — because clusters are just ordinary tree nodes.
  The cost moves entirely onto edits, kept **O(delta)**.

**Decision & reasons.** We chose grafted real groups. At 1M images the hot path
(render/scroll/iterate/select) dominates, and the derived overlay re-pays O(|empty|)
there on every frame-ish event while also forcing a second rendering/iteration path
that doesn't share the tree's. Grafting reuses one code path (the property tree is
already the sole owner of slot storage, sort, filter and iterators) and pushes all
cost to the moments the user actually edits. The flat-peer G3 display also comes for
free: the grafted cluster nodes already sit at the leaf level beside the value-groups.

**Ownership.** Clusters live in a dedicated **`ClusterManager`** (extracted from
`GroupManager` per `collection_inspection_mission.md`), which owns the `customGroups`
registry and every structural cluster op, delegating the low-level tree-mutation
primitives back to the `GroupManager` via a host interface. `GroupManager` stays a
pure property-tree engine.

### The three O(delta) primitives (`ClusterManager`)

- **`clusterEmptyBucket(bucketId, groups)`** — graft `groups` under the empty bucket
  and materialise a **real leftover "No cluster" group** (`GroupType.Cluster`,
  `isLeftover`) holding any undecided image no cluster covered, so the remainder is
  always a visible, routable node — never a per-render derivation.
  > **Built, but unreachable.** The method exists on `ClusterManager` (and is
  > delegated by `CollectionManager`) and nothing calls it: the card grid clusters
  > through the generic `cluster()` → `applyClusters` → `addCustomGroups` path, which
  > treats the empty bucket like any other leaf and materialises the same leftover.
  > Its one distinguishing act is setting `ClusterManager.emptyBucketId`, which
  > nothing reads. The leftover pile itself **is** real and does work — see below.
- **`drain(groupId, instanceIds)`** — the assign primitive (D5). The drained
  instances just got the target value, so pull their slots out of the cluster *and*
  the empty bucket; `updateSelection` adds them to their value-group when the write
  reflows the tree. A fully-emptied cluster detaches. No regroup.
- ~~**`reconcile(updated, groupBy)`**~~ — **Not built.** The design intent was: target-value
  changes from *anywhere* (this view, another view, undo) react in O(|updated|), gated to
  the target property, while `updateSelection` leaves clusters otherwise untouched so a
  write to a **non-target** property never disturbs the piles (G4).
  *As built,* the third primitive is **`ClusterOverlay.resyncDirty(dirtyGroupIds)`**, and
  it is gated differently: on the **dirty group ids** — the buckets the edit moved
  instances in or out of — not on a property. G4 is still honoured, but by a different
  route: `resync` returns a `fingerprint` comparison, so a pass that produces the same
  picture reports no change and nothing re-renders.

There is **no replay after a rebuild**. `GroupManager.group()` calls
`clusters.resyncAll()`, one pass per container: each walks its bucket's current slots
once and refills the piles from the authored `owner` map. Nothing intersects slot
arrays — membership is authoritative in the map and the piles' `slots` are rebuilt from
it, so images the build excluded are simply not visited and come back when the build
includes them again. The queue-drain is a separate, **reversible** mechanism:
`release()` clears the owner and records the pile in a `drained` array, and the next
`resync` honours that record if the image returns.

### What each interaction costs

| Interaction | Cost | Notes |
|---|---|---|
| Render / scroll / iterate / select | O(0) extra | clusters are ordinary tree nodes |
| Open / switch target | rebuild the property tree (grouping change) | new target |
| Cluster the empty bucket | graft nodes + one pass to compute leftover, O(\|empty\|) | one-off per clustering |
| **Assign cluster (bulk)** | `drain`: write O(\|cluster\|); slots leave cluster + empty; value-group gains them | queue-drain, O(delta) |
| Target value change elsewhere | `resyncDirty`, O(\|touched buckets\|) | one refill pass per bucket the edit touched |
| Drag image → value-group | write value; tree re-routes it on reflow | O(delta) |
| Drag image → `empty` cluster | clear value (if any) + move membership | O(delta) |
| Filter / Sort | mask / re-`setOrder` over the tree | no cluster recompute |
| Grouping change | rebuild + `resyncAll` (one refill pass per container) | new target. Appending a level moves each container down one level first (one pass over its old bucket's slots to release the valued ones); removing or reordering a level calls `clusters.clear()`, so the containers go with it |

There is **no per-cluster homogeneity/badge scan** — the paradigm removed `mixed`,
so a value-group simply displays its value and a cluster displays its count. That
whole cost class (and the `clusterOverlay` derive/badge module) has been removed
from the code.

### Memory

- Cluster `Group` nodes' slots total ≤ the undecided working set (they partition
  `empty`) — not 1M each; they shrink as you drain `empty`.
- No cloned parallel `index` / `orderedIds`: the clusters are grafted into the one
  collection tree, which already owns slot storage, sort, filter and iterators.

## Ownership / sequencing

Clusters live in a dedicated **`ClusterManager`**, extracted from `GroupManager` so the
engine stays a pure property-tree builder; the authored membership lives in the
**`ClusterOverlay`** it owns, one `ClusterContainer` per clustered grouping leaf. Not
specialised to the `empty` bucket: any grouping leaf can be clustered, and sub-clusters
of a pile live in the same container (depth is the node table's `up` links). The
`GroupIterator` / `ImageIterator` live on the result object (same mission, §2). The
view renders from the collection tree with the clusters grafted into it — there is no
separate clone and no `rootedAt()`.

## Resolved

- **Target vs. grouping** → unified: the target *is* the leaf grouping property;
  assigning is grouping. One selector. The view no longer requires a grouping
  property: with none, the root is the one card, and the target is chosen late
  ("Assign to…" → group by it). Appending a leaf level moves the clusters into the
  new `empty` child instead of clearing them, so nothing clustered is lost by it.
- **`mixed` groups** → eliminated by construction. A group is a value-group or the
  `empty` (undecided) bucket. No homogeneity scan, no split-by-value, no
  informed-override machinery.
- **Reflow** → intended queue-drain: assignment moves only the acted-on pile out of
  `empty` into its value-group; unworked piles stay put (G4).
- **Drag semantics** → membership follows value (D4): value-group writes its value,
  `empty` cluster undecides, intra-`empty` move is pure membership.
- **The leftover pile** → the un-clustered remainder of the `empty` bucket,
  materialised as a **real "No cluster" group** node (`isLeftover`) grafted beside
  the clusters, so it is always visible and routable — not a per-render derivation.
- **Where clusters live** → **grafted as real `Group` nodes** into the property tree
  (not a derived Set overlay), so render/scroll/iterate/select are O(0) extra and only
  edits cost anything (O(delta)). See *Performance & data flow* for the trade-off.
- **Saving clusters** → assign a value (drains into a persistable value-group). Built:
  each card carries a typed property input per grouping level
  (`ClusterLine` → `GroupView.assignClusterValue` → write, `settle()`, `drainCluster`).
  **Not built yet:** the one-click button that creates a default value per cluster
  (e.g. a tag `Cluster N`) and assigns it, saving all clusters at once.

## Open questions

None on the design — all resolved above. What is **not built** is marked inline and
collected in `README.md` §Open work: no `reconcile` (`resyncDirty` covers the case
differently), no reset button, no save-all-clusters button, drag limited to the
inspector panes, and `clusterEmptyBucket` / `merge` / `delete` / `renameGroup`
implemented but reachable from no UI.
