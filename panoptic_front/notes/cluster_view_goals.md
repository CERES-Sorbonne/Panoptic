# Cluster View — goals and functionalities

Definitive design note for the cluster view — its goals and the settled choices.
Architecture context: `collection_inspection_mission.md` (clusters as a source of
truth separate from the property tree).

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

- **The view always has at least one grouping property.** The leaf grouping level
  is the target; with no grouping there is no target. Picking a target at the root
  is therefore the act of *grouping by it* (which materialises the buckets below).
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

### Scenario 4 — A second, finer property under the first (G1)

Grouped by `Animal`; now you want a `Breed` under `cat`.

- Use **nested grouping**: `Animal → Breed`. The leaf — hence the target — is now
  `Breed`. Inside `Animal = cat` you get the existing breeds plus a `Breed`-`empty`
  bucket.
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
| **Value change on the target from elsewhere** | `reconcile`: images gaining a value drain out of their cluster; images losing it return to the leftover pile in `empty`. O(\|updated\|) |
| **Explicit cluster edit** (cluster / drag / merge / delete inside `empty`) | the only thing that *structurally* mutates the cluster set |
| **Grouping change** (add/remove/reorder group-by, i.e. change the target) | **rebuild** — a new leaf target means new value-groups and a fresh `empty` to cluster |

**Reset button.** Always available to rebuild from the current tree (clean slate):
re-derive the value-groups and re-cluster (or clear) the `empty` bucket. Also the
escape hatch for "I filtered to a subset specifically to cluster it — rebuild for
this filtered set" when the mask default isn't wanted.

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
- **`drain(groupId, instanceIds)`** — the assign primitive (D5). The drained
  instances just got the target value, so pull their slots out of the cluster *and*
  the empty bucket; `updateSelection` adds them to their value-group when the write
  reflows the tree. A fully-emptied cluster detaches. No regroup.
- **`reconcile(updated, groupBy)`** — target-value changes from *anywhere*
  (this view, another view, undo). `updateSelection` deliberately leaves clusters
  untouched so a write to a **non-target** property never disturbs the piles (G4);
  `reconcile` closes the one case that must react: gained a target value → drain out;
  lost it → route into the leftover pile. Gated to the target property only.

`reapplyAfter` re-grafts the saved clusters after a property-tree rebuild, and
**intersects** each cluster's slots with its parent's current slots — the same
queue-drain mechanism during rebuilds (drained images fall out automatically;
emptied clusters aren't re-grafted).

### What each interaction costs

| Interaction | Cost | Notes |
|---|---|---|
| Render / scroll / iterate / select | O(0) extra | clusters are ordinary tree nodes |
| Open / switch target | rebuild the property tree (grouping change) | new target |
| Cluster the empty bucket | graft nodes + one pass to compute leftover, O(\|empty\|) | one-off per clustering |
| **Assign cluster (bulk)** | `drain`: write O(\|cluster\|); slots leave cluster + empty; value-group gains them | queue-drain, O(delta) |
| Target value change elsewhere | `reconcile`, O(\|updated\|) | drain-out / route-to-leftover |
| Drag image → value-group | write value; tree re-routes it on reflow | O(delta) |
| Drag image → `empty` cluster | clear value (if any) + move membership | O(delta) |
| Filter / Sort | mask / re-`setOrder` over the tree | no cluster recompute |
| Grouping change | rebuild + `reapplyAfter` (slot-intersection drain) | new target |

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

Clusters live in a dedicated **`ClusterManager`** (the `ClusterRegistry` idea from
`collection_inspection_mission.md`, specialised to the `empty` bucket of the leaf
target), extracted from `GroupManager` so the engine stays a pure property-tree
builder. The `GroupIterator` / `ImageIterator` live on the result object (same
mission, §2). The view renders from the collection tree with the clusters grafted
into it — there is no separate clone and no `rootedAt()`.

## Resolved

- **Target vs. grouping** → unified: the target *is* the leaf grouping property;
  assigning is grouping. One selector. The view requires ≥1 grouping property.
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
- **Saving clusters** → assign a value (drains into a persistable value-group);
  plus a button that creates a default value per cluster (e.g. a tag `Cluster N`)
  and assigns it, saving all clusters in one click.

## Open questions

None currently — all resolved above.
