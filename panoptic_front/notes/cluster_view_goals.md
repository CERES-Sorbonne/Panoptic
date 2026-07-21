# Cluster View — goals and functionalities

Definitive design note for the cluster view — its goals and the settled choices.
Architecture context: `collection_inspection_mission.md` (clusters as a source of
truth separate from the property tree).

The cluster view is not a consultation view — it is a **tool for producing and
fixing property values**. Clustering is scaffolding; the durable output is the
property values written onto the instances.

## Goals

- **G1 — Assign property values fast, in bulk.** The end goal is to group / filter
  / sort images by value, but the values have to exist first, and setting them one
  image at a time is slow. Cluster visually similar images, then give a value to a
  whole cluster at once.
- **G2 — Correct an existing grouping.** Move mis-grouped images between groups
  (inspectors + drag-and-drop) to fix wrong values. Clustering/inspection makes
  outliers stand out visually (a dog among cats), which the flat main tree hides.
- **G3 — Focus on one level.** Show all leaf sub-groups of the current level, no
  depth or parent indication. Avoids the "close 1000 groups to see one" problem of
  the full tree, and stays cheap at ~1M images.
- **G4 — Stable while working.** Clusters must not jump around under the user
  while assigning. This needs no staging: assignments write **directly**, but the
  target is a *non-parent* property (D1), so a write doesn't reflow the view — the
  badge just updates in place. Only explicit cluster edits and grouping changes
  restructure.

## Example scenarios and how they're solved

### Scenario 1 — Label an unclustered collection with a new property (G1)

No active grouping. You cluster the whole collection and want to tag each cluster,
e.g. `Animal = cat / dog / bird`.

- Pick the **target property** in the toolbar (`Assign → Animal`). This is the
  only thing that's undetermined here — not the grouping.
- Each cluster shows a **badge** of its current state on `Animal`: `empty` (no
  value) or `mixed` (several). Both mean "to do."
- Assign a value to each cluster (the **badge**, bulk over the whole group). The
  write is **direct** — the badge flips `empty`/`mixed → cat` in place, and since
  `Animal` isn't the view's parent, nothing reflows.

### Scenario 2 — Fix a grouping that already exists (G2)

Grouped by `Animal`. Some images are in the wrong group (a dog labelled `cat`).

- Open two value-groups in the two **inspectors** (`cat` and `dog`).
- Spot the outlier — it stands out visually among its neighbours — and **drag** it
  from `cat` to `dog`. Dropping into the `dog` group rewrites that image's
  `Animal` value to `dog`.
- Assigning the *same* property as the grouping is **not** redundant: the badge
  has nothing to do (groups are already homogeneous) but the drag is doing the
  real work.

### Scenario 3 — One clustering, several different attributes (G1)

Clustering is unsupervised, so different clusters are homogeneous on *different*
properties: one cluster is all black-and-white (`ColorMode`), another all
portraits (`ShotType`), another all watermarked (`Quality`).

- Solved by **sequential passes**, not by showing many properties at once: pick
  `ColorMode`, sweep and assign the clusters that are about it; switch target to
  `ShotType`, sweep again; etc.
- Between passes you may **re-cluster** — a different clustering can suit the next
  property better. Re-clustering **always nests** the new sub-clusters under the
  group (never split-and-replace in place); badges are derived, so they recompute
  for the new sub-clusters automatically.
- A cluster that is both "B&W" and "portrait" gets both labels, in different
  passes, never two badges at once (keeps cards fixed-size — see D2).

### Scenario 4 — Cluster inside an existing grouping, assign another property (G1)

Grouped by `Animal`; you cluster within the `cat` group and want to add a
`Breed`.

- Clusters sit under a single `Animal` value, so they inherit it — but that's a
  *different* property from the one you assign.
- Set target to `Breed`; badges are `empty`/`mixed`; assign per cluster (writes
  directly, no reflow — `Breed` isn't the parent).
- The inherited `Animal` value is untouched — orthogonal axes (D1).

### Scenario 5 — Several labels on the same image at once (G1)

You want an image to carry "beach", "sunset" and "crowd" simultaneously.

- Use **one tag-type property** holding multiple values — still a single active
  target, single badge area, single column.
- We do **not** solve this with multiple properties assigned at once (D2).

### Scenario 6 — User switches target and the groups don't match it (avoids confusion)

After Scenario 1 the user switches the target to a property the clusters were
never built around; a cluster holds mixed values of it.

- The picker is framed as a **verb** (`Assign → C`), visually distinct from the
  grouping selector, so groups are never read as "C groups."
- Each group shows a **`mixed` chip** (icon + count, fixed size) — which is
  exactly the thing to resolve, not an error. Assigning collapses `mixed → x`.
- Because the badge plainly shows "current state of the property I'm assigning,"
  the groups having no reality on C is *displayed as* no reality; the user is
  never misled into thinking they do.
- Switching the target **keeps** the current clustering — no forced re-cluster.
  The `mixed`/homogeneous badge on the new target conveys the state; re-clustering
  stays optional (Scenario 3).

## Design invariants that make the scenarios work

- **D1 — Cluster and property-group are orthogonal axes.** Clusters are manual,
  structural, stable, and *not* reactive to values (the code confirms:
  `updateSelection` skips `Cluster` groups, their `imageToGroups` persists across
  value changes, the view runs on a standalone `GroupManager` with no `groupBy`).
  So assigning a value writes onto instances without dissolving the clusters here;
  it only reflows the *main* view if that view is grouped by the same property.

- **D2 — One active target property at a time.** No simultaneous multi-property
  assignment: it would force variable-height cards, and at ~1M images the virtual
  scroller needs line heights known **without measuring** — fixed-size cards are a
  structural requirement, not an aesthetic. Multiple properties → sequential
  passes (Scenario 3); multiple simultaneous labels → tag-type property
  (Scenario 5).

- **D3 — A grouping is just a property already assigned.** `mixed` vs.
  single-value measures a group's homogeneity on the target. Target = grouping
  property → homogeneous everywhere (bulk-assign has nothing to do, but
  drag-correction applies). Target = any other → mixed/empty → work to do. Hence
  no need to force a grouping first; "switch target" reads as "which property to
  resolve/refine next?"

- **D4 — Drag semantics fall out of the destination.** Dropping an image into a
  group gives it that group's meaning: into a **property-value group** rewrites
  that property (correction); into a **cluster** is pure membership, no write
  (today's `moveImagesToGroup`).

- **D5 — Direct writes, no staging (G4).** Badge assignment writes to the
  instances immediately — there is no pending state and no write button. It's safe
  because the target is a non-parent property (D1), so the write doesn't reflow the
  cluster view; the badge just updates in place. Corrections that *do* move images
  use drag, an explicit cluster edit (Scenario 2).

## Persistence — clusters are ephemeral, values are durable

**A group survives a reload only if it is identified by a property value.**
Value-less clusters, and sub-divisions that don't map to a distinct value, are
**not persisted** — they vanish on reload. Clusters are an *on-the-moment*
grouping: a session-scoped working tool, not saved state.

To **save** a cluster, link it to a property value (assign it a value). That
converts the ephemeral scaffolding into a value-group, which *is* reproducible
from data and therefore survives reload. This is the whole thesis made concrete:
clusters are scaffolding, property values are the durable output.

Consequence: we don't engineer cluster membership to survive **undo** either.
**Undo applies to commits only** (committed property values / data). Cluster
structure is not on the undo log; if an undone commit changes what a group
contains, the view simply recomputes its display from the current data (below).

## Reactivity & sync

**Assumption:** no concurrent multi-user editing of the same images/property — by
convention users work on different images/properties. The realistic case is *we
ourselves* change a property in another view; we know when we do it, so the view
reflowing in response is expected, not a surprise.

Because clusters are ephemeral, the reaction is minimal — membership maintenance
only, never re-clustering. The reaction depends on what changed:

| Change | Effect on clusters |
|---|---|
| **Sort** | none — display order only |
| **Filter** | **mask**: hide members not passing, keep the cluster set intact (reversible, instant) |
| **Value change** | recompute displayed membership: drop members no longer in parent P; P's now-uncovered images go to the **no-cluster** group |
| **Explicit cluster edit** (cluster / drag / merge / delete) | the only thing that *structurally* mutates a cluster set |
| **Grouping** (groupBy add/remove) | **reset all clusters** — it restructures which parents exist, so the nesting is meaningless |

The displayed clusters are therefore *derived*: `cluster set ∩ current parent P ∩
filter`, with the no-cluster group holding P's covered-by-nothing images. The
cluster sets themselves change only through explicit cluster edits (or a full
reset). This is O(delta), deterministic, and runs where `updateSelection`
currently *skips* clusters (`type == Cluster` → continue).

**Root vs. nested:**

- Root clusters (no grouping) — P is the collection, so value changes never
  invalidate membership (an image only leaves by deletion); only new-to-collection
  images land in no-cluster.
- Nested clusters — value changes matter, and only when the *parent* property
  changes; assigning a *different* property (the normal case) invalidates nothing.

**Direct writes don't reflow (D5 / G4):** a badge assignment commits immediately,
but because the target is a non-parent property it invalidates no cluster
membership — the view stays stable through a whole labeling pass. Recompute only
bites on changes to the *parent* property (yours or from another view).

**Reset button.** Always available to rebuild clusters from the current tree
(clean slate). Also the escape hatch for "I filtered to a subset specifically to
cluster it — rebuild for this filtered set" when the mask default isn't wanted.

## Performance & data flow (~1M images)

### What the current flow costs

The cluster view today re-clones on every `version` bump: `rebuildTree()` →
`GroupManager.rootedAt()` deep-clones the selected subtree and rebuilds its
`imageToGroups` by walking every leaf slot. Each structural op in `groupOps.ts`
also runs three O(N) passes:

| Hot path | Cost | Fires on |
|---|---|---|
| `rootedAt()` clone + `imageToGroups` rebuild | O(N slots in subtree) | every version bump (rename, move, **badge assign**, another view's edit) |
| `buildOrdinalRanges()` — fresh `Int32Array` + DFS refill | O(N) | every op |
| `applySha1Piles()` — `Object.values(index)` + pile per **every** leaf | O(N) | every op |
| `moveImagesToGroup` — `from.slots.filter` + `new Set(to.slots)` | O(group) | each drag |

The killer: a **rename** or **badge assign** changes nothing structural yet still
pays a full-subtree clone + full `orderedIds` rebuild + full sha1 recompute over
untouched leaves — O(N) per interaction on a possibly 1M-slot subtree.

### Recommendation — don't clone, derive

The model (ephemeral, one-level, membership-only, display = `clusterSet ∩ parent ∩
filter`) is a *derivation*, not a tree. So drop the standalone `GroupManager`
clone and represent clusters as a thin overlay over the collection tree (the
`ClusterRegistry` idea from `collection_inspection_mission.md`, specialised to one
level).

```ts
interface ClusterSet { id: number; name?: string; slots: Set<number>; isLeftover?: boolean }

interface ClusterOverlay {
  parentId: number
  clusters: ClusterSet[]
  slotToCluster: Map<number, number>   // slot → clusterId ; O(1) routing
}
```

- `Set<number>` (not `number[]`) → explicit edits are O(1) (`add`/`delete`/`has`)
  instead of the current `from.slots.filter` O(group) per drag.
- `slotToCluster` is the routing index that makes everything one pass.

**Ownership.** The overlay lives in a dedicated **`ClusterManager`**, not in
`GroupManager` — clusters come out of `GroupManager` entirely (the goal of
`collection_inspection_mission.md`'s `ClusterRegistry`). The `GroupIterator` /
`ImageIterator` also move out of `GroupManager` onto the result object (same
mission, §2). `GroupManager.rootedAt()` is **removed** — the cluster view renders
from the collection tree + overlay, never a clone. So this section and the
separation mission are the same refactor from two angles; sequence it via the
mission (result object + registry first, then delete the clone).

**The single primitive — one pass over the parent's already-ordered,
already-filtered slots:**

```ts
// parent.slots comes from the collection tree: filtered AND in sort order.
function derive(parentSlots: number[], ov: ClusterOverlay) {
  const lines = ov.clusters.map(c => ({ cluster: c, display: [] as number[] }))
  const byId = new Map(lines.map(l => [l.cluster.id, l]))
  const noCluster: number[] = []
  for (const s of parentSlots) {              // O(|parent|), preserves order
    const cid = ov.slotToCluster.get(s)
    if (cid === undefined) noCluster.push(s)
    else byId.get(cid)!.display.push(s)
  }
  return { lines, noCluster }
}
```

Iterating `parent.slots` means the output is **already filtered** (parent.slots is
the filtered set) and **already sorted** (parent is in display order) — filter-mask
and cluster ordering are free, no per-cluster sort, no separate `orderedIds`. The
no-cluster bucket falls out of the same pass.

### What each interaction costs (proposed)

| Interaction | Cost | vs. today |
|---|---|---|
| Open / switch cluster | one `derive`, O(\|parent\|) | replaces full clone O(N) |
| **Badge assign (bulk)** | write O(\|cluster\|); set badge = value directly; **no derive, no structural change** | replaces clone + ordinals + sha1, all O(N) |
| Drag image A→B | `A.slots.delete(s)`, `B.slots.add(s)`, `slotToCluster.set(s,B)`; re-render 2 lines | O(1) vs O(group) filter + O(N) |
| Filter change | one `derive` over new `parent.slots`; Sets untouched | avoids clone |
| Value change on **parent** property | `derive` handles it: departed slots vanish, new ones route to no-cluster | automatic |
| Sort change | re-`derive` (or re-read order) | O(\|parent\|) vs O(N) |
| Grouping change | reset overlay | — |

The recurring O(N) passes collapse to **one O(\|parent\|) derive**; the two common
actions (badge assign, drag) become O(1)/O(cluster) with **no reflow** — D5/G4,
now actually cheap.

### Badge (`mixed` / homogeneous / empty) computation

The one new scan. Per visible cluster, per target property:

```ts
// early-exit on first differing value → 'mixed' is cheap to detect
function badge(cluster: ClusterSet, buf): BadgeState {
  let first, hasFirst = false
  for (const s of cluster.slots) {
    const v = buf[s]
    if (!hasFirst) { first = v; hasFirst = true }
    else if (v !== first) return { kind: 'mixed' }
  }
  return hasFirst ? (first == null ? { kind: 'empty' } : { kind: 'value', v: first })
                  : { kind: 'empty' }
}
```

- **Homogeneity rule:** if any two instances differ on the target property → `mixed`;
  otherwise show the common value. For a **tag-type** (set-valued) target, "differ"
  means set-inequality — compare via a canonical form (sorted ids), since `v !== first`
  reference-compares arrays.
- **Lazy, viewport-only** — the scroller is virtualized, so cost is bounded by
  what's on screen, not total clusters.
- **Bulk-assign shortcut** — after writing `v` to a whole cluster the result is
  known (`{ value: v }`); set it directly, never scan → O(1) write path.
- Cache per `(clusterId, targetProp)`; invalidate only when that cluster's `slots`
  change or the target switches.

### Reactivity gating

Replace the blunt `watch([group, version])` (recomputes on any change anywhere)
with three targeted triggers:

- **parent `slots` identity/length changed** → re-`derive` (filter/sort/parent-value).
- **target property changed, or a write touched the target on a visible cluster** →
  recompute those badges only.
- **explicit cluster edit** → mutate the `Set` + re-render affected lines.

A write to an unrelated property, or a change elsewhere in the tree, does nothing.
Since `version` is a single global tick, gate the handler with a cheap check (did
`parent.slots` change? was the written prop the target?) before doing work.

### Memory

- Registry `Set`s total ≤ the working set (clusters partition `parent.slots`) — not
  1M each.
- `slotToCluster` as a `Map` is fine; flat `Int32Array(maxSlot+1)` filled with `-1`
  is ~4 MB at 1M — O(1), GC-friendly.
- **No second `GroupManager`, no cloned `index` / `imageToGroups` / `orderedIds`** —
  the biggest win vs. `rootedAt`. The collection tree stays the sole owner of slot
  storage, sort, and filter; the overlay adds only membership Sets + routing.

### Resolved

- **Ownership / iterators / clone** → a dedicated `ClusterManager`; iterators move
  out of `GroupManager`; `rootedAt()` removed. Sequenced via
  `collection_inspection_mission.md`.
- **Badge homogeneity** → differ ⇒ `mixed`, else common value (set-equality for
  tag targets).
- **Re-cluster** → always nests; never split-and-replace.
- **The leftover "no-cluster" pile** → a **real group with a predictable, reserved
  id** (per-overlay constant, or derived from `parentId`), but with **derived
  membership**: the `derive` pass pushes unrouted `parent.slots` into
  `leftover.slots` instead of a separate `noCluster` array. This keeps downstream
  code uniform (same id / badge cache / drag target / selection / assign path as any
  cluster — no special-casing) while avoiding any maintained Set. It re-fills only
  when the parent set changes (filter / sort / parent-property value), **not** on
  ordinary target assignments — those just refresh its badge, like any cluster.
  (Only exception: a filter *on the target property* moves images out of the parent,
  re-derived via the same filter trigger.) Replaces today's `getTmpId()` +
  `children.find(c => c.isLeftover)` lookup with a direct known-id lookup.
- **Saving clusters** → keep the implicit path (assign a value → group-by
  reproduces the set), **plus a button that creates a default value per cluster**
  (e.g. a tag `Cluster N`) and assigns it, so all clusters can be saved in one
  click without manual property setup.

## Open questions

None currently — all resolved above.
