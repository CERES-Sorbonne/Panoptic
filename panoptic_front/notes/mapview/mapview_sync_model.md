# The synchronisation model — the map is a projection of the result tree

The premise: **every view shows the same result tree**. A view differs from another only in
*where it puts a group on screen* and *what it lets you do to it* — never in which groups
exist, who is in them, or what state they're in.

- `TreeScroller` lays the tree out **vertically**, position = DFS order.
- `ClusterScroller` (group view) lays the **leaf frontier** out as a **card grid**, position
  = index in the level.
- `MapView` lays the same groups out **spatially**, position = the embedding's `(x, y)`.

So the map is a *layout function* over `GroupResult`, exactly as `computeLines` is. Anything
the map derives that isn't `(x, y)` should come from the same place the scrollers get it.

---

## 1. The missing shared concept: the visible frontier

Every view already answers, in its own private code, the question *"which groups currently
stand for this collection?"* — descend through **open** groups; a **closed** group stands in
for its whole subtree.

- `GroupView.counts.walkVisible` (`GroupView.vue:57`) does it to count cards.
- `ClusterScroller` / `TreeScroller` do it structurally while building lines.
- `MapView` doesn't do it at all — it hard-codes "the root's children" (see
  `mapview_current_state.md` §B).

**Proposal — extract it once**, `src/core/group/frontier.ts`:

```ts
// The groups that currently stand for the collection: descend through open groups,
// stop at a closed one (it stands in for its subtree). The set every view colours,
// counts or lays out — the map's regions, the group view's cards, the tree's top level.
export function visibleGroups(result: GroupResult, opts?: {
    root?: number          // frontier of a subtree (map focus mode / an inspector pane)
    maxDepth?: number      // stop early regardless of open state
}): Group[]
```

and a companion the map specifically needs:

```ts
// slot → index into the frontier array (-1 = covered by no frontier group).
// One O(sum of frontier slots) pass; this is the map's `computeLines`.
export function frontierIndex(groups: Group[], slotCount: number): Int32Array
```

Once the map colours by `visibleGroups()`, synchronisation stops being a feature and becomes
a consequence:

| user does | tree pane | map pane |
|---|---|---|
| no grouping | one flat list | one neutral region (colour = selection only) |
| group by `Animal` | `cat` / `dog` / `empty` headers | three coloured regions |
| open `empty`, cluster it (group view) | cluster rows under `empty` | `cat` / `dog` / `cluster 1..n` / `No cluster` |
| close `empty` again | one `empty` header | the clusters re-merge into one region |
| nested `Animal → Breed`, open `cat` | breeds under `cat` | `dog`, `empty`, and `cat`'s breeds as peers |

That last row is worth stating plainly: **the map inherits nesting for free** and never has
to render depth — spatially, a frontier is just a set of peers, which is exactly G3 of
`cluster_view_goals.md`.

---

## 2. The contract, aspect by aspect

| Aspect | Source of truth | Today | Proposed |
|---|---|---|---|
| **Which images** | `result.root.slots` | `filterManager.result.slots` (`MapView.vue:256`) | `manager.result.root.slots` |
| **Which groups** | `visibleGroups(result)` | `root.children`, filtered by type | the frontier |
| **Open / close** | `Group.view.closed`, `openGroup`/`closeGroup` | ignored | read it; legend double-click writes it |
| **Group identity** | `Group.id` (stable across rebuilds via `valueIndex`) | `Group.id` ✓ | unchanged — keep using ids as the join key with the other panes |
| **Membership** | `group.slots` (+ `pileIndex` overlay) | `group.slots`, de-duped by sha1 locally | `pileIndex` for the sha1 fold; slots stay authoritative |
| **Counts** | `group.slots.length` / `pile.order.length` | sha1 count (disagrees) | same rule as the scrollers |
| **Selection** | `columnStore`, namespaced | `global`, hard-coded | `manager.selectionNamespace` |
| **Clustering** | `ClusterManager` via `manager.cluster(groupId, req)` | root-only, silently bails when grouped | the same target the group view uses |
| **Colour** | *(nowhere yet — see §4)* | local `generateColors` + tag colours | one shared `groupColor(group, idx)` |
| **Hover** | *(nowhere yet — see §3)* | view-local `hoverInstanceId` | shared per-tab hover |
| **Sort order** | `SortManager` | ignored | **stays ignored** — position comes from the embedding |
| **Filter** | `FilterManager` → root membership | full geometry rebuild | a per-point **visibility mask**, geometry untouched (§5) |

Two deliberate non-syncs:

- **Sort** is the one axis a map legitimately cannot honour. Say so in code, so nobody
  "fixes" it later.
- **Scroll position / camera** are per-view. Panning the map must not move the tree. The
  *explicit* jump gestures (legend click → `lookAtRect`; a future "reveal in tree") are the
  supported bridge.

---

## 3. Shared hover

The map already computes a hovered instance (`SpatialIndex` → `onHover`) and throws it away
locally. The scrollers have no hover concept at all. The highest-value cheap sync in the
whole proposal is the pair:

- hover a point → the corresponding row/cell highlights in the tree/grid pane;
- hover a cell in a scroller → its point pulses on the map.

This needs a tiny piece of shared state and nothing else. Two candidate homes:

- **`columnStore`**, alongside selection — one `hoveredInstanceId` ref plus a tick. Cheap,
  global, matches how selection already works, but it is a *view* concern in a data store.
- **A per-tab `useHoverState(tabId)` composable** — correct scope (two tabs shouldn't share
  a hover) and it keeps the store clean. Slightly more plumbing.

Recommendation: the per-tab composable. Hover is view state, and the notes have already
decided once that view state doesn't belong on the data/tree objects.

Note the existing subtlety worth keeping: `lastValiderHoverId` (`MapView.vue:41`) holds the
last non-null hover so the preview doesn't blank when the cursor crosses empty space. Any
shared hover needs the same "sticky preview, live highlight" distinction — i.e. two values,
not one.

---

## 4. One colour rule, three views

Today the map is the only view that assigns a colour to a group, and it does it inline. If
the map's colours are going to mean anything next to the tree, the rule has to be shared:

```ts
// src/core/group/groupColor.ts
// A group's colour: its tag colour when it is a tag value-group, the palette entry for its
// position in the frontier otherwise. Deterministic in (group, index) so the legend, the map
// and a future coloured group header always agree.
export function groupColor(group: Group, index: number, palette: string[]): string
```

The existing logic in `generateGroups` (`MapView.vue:205`) is already this function, minus
the extraction. Once shared, the group view's cards and the tree's group headers can pick up
the same accent for free — which turns out to be a bigger legibility win than the map itself.

**Constraint the frontier introduces:** palette index must be stable while you work. Deriving
it from array position means opening one group re-colours every group after it. Derive it
from the group's position **among its siblings** (or hash the group id) so a local change
stays local.

---

## 5. What "same tree" costs, and where the cost has to go

The map's honest problem is that colouring is per-*point*, i.e. O(n), while a scroller only
ever touches the visible window. So the split that matters:

| Layer | Depends on | Rebuild when |
|---|---|---|
| **Geometry** (`PointData[]`, `sha1 → point`, GPU buffers) | selected map + atlas | the map or the atlas changes — **only** |
| **Visibility mask** | `root.slots` | filter changes / instances added or removed |
| **Region index** (`slot → frontier idx`) | the frontier + membership | structural tree change (group, cluster, open/close, drag) |
| **Colour / tint / z** | region index + selection + hover | any of the above, plus every selection tick |

Today all four are fused into `showMap` + `createMap` (`mapview_current_state.md` §C). Split
them and the cost model becomes:

| Interaction | Today | Split |
|---|---|---|
| Open / close a group | full geometry rebuild + GPU re-upload | region index + recolour |
| Cluster / drag / assign | full rebuild | region index + recolour (and only dirty groups moved) |
| Selection change | recolour (already) | recolour, scoped to the namespace's delta |
| Filter change | full rebuild | flip the visibility mask; positions untouched |
| Sort change | full rebuild | **nothing** |
| Choose another map | full rebuild | full rebuild (correct — the points genuinely moved) |

The one change this needs *below* the Vue layer: `MapRenderer` needs a per-point
**visible** flag it can honour without a `createMap`. Everything else is already there —
`updateBorder` / `updateTints` / `updatePosition` write into existing buffers.

Later, if the O(n) region pass ever shows up in a profile, it has an obvious O(delta)
successor: `updateSelection` already knows which groups are dirty, so the region index can be
patched over `group.slots` of the dirty frontier groups only — the same move `drain` and the
scoped `applySha1Piles` already made. **Don't build that first**; a typed-array pass over
1M slots is a few milliseconds and only runs on structural change.
</content>
