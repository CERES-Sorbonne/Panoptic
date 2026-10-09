# More Optimisations — GroupManager + TreeScroller

Scope: `panoptic_front/src/core/GroupManager.ts` + `panoptic_front/src/components/scrollers/tree/TreeScroller.vue`.

Current pain points:
1. **Multi-grouping that yields lots of tiny groups (~1 slot each) is slow.** Recursive subgroup computation + per-subgroup work dominates.
2. **`computeLines()` throws `Maximum call stack size exceeded`** when a single group produces a very large `GroupToLines(...)` result (large group with many image lines, or narrow window forcing many lines per group).

The two issues are independent; both can be fixed without large architectural changes.

---

## 1. Stack overflow in `computeLines` — the bug

`TreeScroller.vue:180`

```ts
lines.push(...GroupToLines(it))
```

`GroupToLines` returns the group line **plus every image/pile line for that group**. A group with N images and width W produces `1 + ceil(N / imagesPerLine)` lines. With narrow windows and big groups, this array can be tens or hundreds of thousands of entries. `Array.push(...arr)` spreads the array as **function arguments**, which hits the engine's argument count limit (~64k–500k depending on engine) and throws `RangeError: Maximum call stack size exceeded`.

### Fix A — Drop the spread (minimal change)

```ts
const sub = GroupToLines(it)
for (let i = 0; i < sub.length; i++) lines.push(sub[i])
```

### Fix B — Skip the intermediate array (preferred)

Refactor `GroupToLines` / `computeImageLines` / `computeImagePileLines` to accept the output `lines` array and push into it directly. Avoids one allocation per group and removes the failure mode entirely.

```ts
function appendGroupLines(it: GroupIterator, lines: ScrollerLine[]) {
    const group = it.group
    lines.push({ id: group.id, type: 'group', data: group, depth: group.depth,
                 size: props.hideGroup ? 0 : 30, nbClusters: 10 })
    if (group.children.length > 0 && group.subGroupType !== GroupType.Sha1) return
    if (group.view.closed) return
    if (group.subGroupType !== GroupType.Sha1) {
        appendImageLines(it, lines, ...)
    } else {
        appendPileLines(it, lines, ...)
    }
}
```

This also eliminates `lines.push(...)` inside `computeImageLines` (line 217) — the `addLine` helper pushes into `lines` directly already, so this part is fine, but the outer wrapper is the problem.

---

## 2. Multi-grouping with many small groups — `computePropertySubGroup`

`GroupManager.ts:883`

### What's expensive today

For each recursion level the function:
- allocates a fresh `buckets: Map`, `bucketMeta: Map`
- if tag-typed, **rebuilds `tagWithParents` for the property** (line 896–902)
- single pass over `group.slots`, then per unique bucket allocates a `Group` and `key = group.key.concat([kv])`
- calls `sortGroup` at the tail
- recurses on every child

When grouping yields fan-out × levels (e.g. 3 properties → 50k → 50k tiny leaves), this means:
- **`tagWithParents` is recomputed N times for every sibling at the same level** (same property → same map).
- **N `Map` allocations** at each level, most of them small/empty.
- N `sortGroup` calls on `children.length ≤ 1`.
- N `setChildGroup` / `addChildGroup` calls with all their per-child bookkeeping.

### Optimisation 2.1 — Hoist `tagWithParents` (biggest cheap win)

Build once per groupBy property at the top of `group()` and pass down. Same applies to `addInstanceToGroups` (line 472) where `tagWithParents` is rebuilt **per slot per property** — that's O(slots × tags) wasted.

```ts
// In group(), before computePropertySubGroup:
const tagWithParentsByProp = new Map<number, Record<number, Set<number>>>()
for (const propId of this.state.groupBy) {
    const property = data.properties[propId]
    if (!isTag(property.type) || !property.tags) continue
    const map: Record<number, Set<number>> = {}
    for (const tag of objValues(property.tags)) {
        const s = new Set(tag.allParents); s.add(tag.id)
        map[tag.id] = s
    }
    tagWithParentsByProp.set(propId, map)
}
```

Thread through `computePropertySubGroup` and `addInstanceToGroups`.

### Optimisation 2.2 — Single-pass multi-level bucketing

The recursion is unnecessary for the property path. The work decomposes as: every slot has a **path vector** `(v_1, v_2, …, v_k)` across the groupBy properties; we want all unique path prefixes to become groups. One traversal can do this:

```ts
// Map<v1, Map<v2, ...Map<vk, slot[]>>>
// or: flat Map<compositeKey, slot[]> with the GroupValueIndex providing IDs.
```

Sketch (non-tag, single-value case — generalises to tag via per-level fan-out):

```ts
const root = this.result.root
const groupByProps = this.state.groupBy.map(id => data.properties[id])
const parsers = groupByProps.map(p => valueParser[p.type])
const rawBufs = groupByProps.map(p => col.getRawBuffer(p.id))

// One walk over root.slots.
for (const s of root.slots) {
    let level = root
    for (let i = 0; i < groupByProps.length; i++) {
        const kv = parsers[i](rawBufs[i]?.[s])
        // find-or-create child of `level` with key kv, then descend
        ...
    }
    // when at leaf, push slot
}
```

This collapses `Σ levels × subgroups × allocations` into one pass + one allocation per *created* group (vs. one allocation per subgroup *call*). Crucially: when many groups are size 1, you allocate one `Group` per slot — unavoidable — but you no longer allocate one `Map` per parent.

The tag-property case fans out per-slot during descent (one branch per resolved tag including parents). Same shape as the current code, just inlined.

Date and tag types keep using `dateBucketKey` / `tagWithParents` from 2.1.

Then call `sortGroup` once per parent in a post-order pass — not from inside the bucketing loop.

### Optimisation 2.3 — Cheap early-outs in `sortGroup` / `sortGroupByProperty`

```ts
function sortGroup(group: Group, option: GroupOption) {
    if (group.children.length < 2) return   // currently checks == 0
    ...
}
```

`sortGroupByProperty` (line 199) builds a `sortable` lookup object keyed by `child.id` (string coerced from number) for every sort. For groups where children have a single `propertyValues` entry, inline the value extraction into the comparator and skip the dictionary build:

```ts
function sortGroupByProperty(group, dir, properties, folders) {
    if (group.children.length < 2) return
    // Precompute a sortKey on each child once.
    for (const c of group.children) c._sortKey = computeSortKey(c, properties, folders)
    group.children.sort((a, b) => cmp(a._sortKey, b._sortKey) * dir)
}
```

Storing on the child avoids the `sortable[child.id]` hash; cleared after sort if you want.

### Optimisation 2.4 — Avoid `group.key.concat([kv])` per bucket

`group.key.concat([kv])` allocates two arrays. Use:

```ts
const key = group.key.slice()
key.push(kv)
```

Per-bucket savings are small individually but compound when there are 100k buckets.

### Optimisation 2.5 — Skip Date allocation in the hot loop (sub-day)

`computePropertySubGroup:916`:
```ts
const bk = dateBucketKey(raw instanceof Date ? raw : new Date(raw as number), option.stepSize, option.stepUnit)
```

For sub-day units (`Second`–`Week`) `dateBucketKey` only needs `.getTime()`. If `raw` is already a number (epoch ms), don't wrap in `new Date()` — call a numeric variant:

```ts
function dateBucketKeyMs(ms: number, stepSize: number, unit: DateUnit) {
    if (unit === DateUnit.Year || unit === DateUnit.Month) {
        return dateBucketKey(new Date(ms), stepSize, unit)  // year/month rare-ish
    }
    const stepMs = (stepSize || 1) * DateUnitFactor[unit] * 1000
    return Math.floor(ms / stepMs)
}
```

### Optimisation 2.6 — Hoist `rawBuf?.` null-check

Inside the scan loop, `rawBuf?.[s]` adds an undefined check per slot. Bail out before the loop if `rawBuf` is `undefined` (treat as "all nulls → no bucket") and read `rawBuf[s]` unguarded inside.

---

## 3. `addUpdatedToGroups` / `updateSelection` — touch dirty groups only

`GroupManager.ts:425, 673`

```ts
for (const group of objValues(this.result.index)) {
    if (group.type != GroupType.Cluster) {
        group.slots.sort(...)
    }
}
```

This sorts **every** group in the tree even though only a few are dirty. With many small groups the cost is O(numGroups) per update just for the loop walk, plus per-group sort overhead.

Maintain `result.dirtyGroupIds: Set<number>` populated by mutations (`addChildGroup`, `addInstanceToGroups`, `updateSelection`, etc.). Reconcile only those:

```ts
for (const gid of result.dirtyGroupIds) {
    const g = result.index[gid]
    if (!g || g.type === GroupType.Cluster) continue
    g.slots.sort((a, b) => this._posArr[a] - this._posArr[b])
    g.dirty = false
}
result.dirtyGroupIds.clear()
```

Same change in `updateSelection`: it already builds a `dirtyGroupIds` Set but then iterates `objValues(this.result.index)` twice afterwards (lines 712, 719). Drive both passes off the same set.

The `imageToGroups` rebuild in `addUpdatedToGroups` (line 450) blows away the entire map and re-fills it. For a small incremental update this is wasteful. Mutate it incrementally: remove old (id → groupId) pairs for the slots that left, add new ones for the slots that joined.

---

## 4. TreeScroller iteration — avoid per-group / per-image iterator allocations

`TreeScroller.vue:176, 205`

Today:
```ts
let it = props.groupManager.getGroupIterator()
while (it) { ...; it = it.nextGroup() }
```

Each `nextGroup()` constructs a new `GroupIterator` (does an `index[groupId]` lookup, initialises `options`, etc.). Inside `computeImageLines`, each `nextImages()` allocates a new `ImageIterator`, which calls `super(...)` (allocates GroupIterator), runs `shouldSkipGroup`, etc.

For 100k groups + N images per group this is a lot of GC pressure.

### Optimisation 4.1 — Direct tree walk for the group pass

We have `result.root`; siblings live in `parent.children`. Walk with a tiny explicit stack (or just recursion since depth = `groupBy.length`):

```ts
function walk(group: Group) {
    appendGroupLines({ group } as any, lines)  // pass the group, not an iterator
    if (group.view.closed) return
    if (group.subGroupType === GroupType.Sha1) {
        // piles: handled below
    } else if (group.children.length > 0) {
        for (const c of group.children) walk(c)
    }
}
walk(props.groupManager.result.root)
```

Zero iterator allocations for the group pass. `nextGroup()` ordering already matches DFS in `setOrder`.

### Optimisation 4.2 — Avoid `ImageIterator` per image in `computeImageLines`

The line packing currently does:

```ts
let imgIt = ImageIterator.fromGroupIterator(it)
while (...) { newLine.push(imgIt); imgIt = imgIt.nextImages() }
```

`nextImages()` constructs a new ImageIterator per image. For groups with many images this is the dominant cost.

Two options:

**(a) Lazy iterator (smaller change):** Store the slot index in the line, not the iterator. Build the iterator on demand inside `ImageLine.vue` / `PileLine.vue` (e.g. on click).

```ts
interface ImageLine {
    type: 'images'
    groupId: number
    slots: number[]      // or a slice of group.slots
    ...
}
```

The line packer becomes a pure numeric loop over `group.slots` (or `group.children` for sha1 piles). Order is preserved by the underlying `group.slots` ordering done in `group()`.

**(b) Pool iterators (no template change):** Keep returning `ImageIterator[]` but pool the objects. Less elegant.

Option (a) requires touching `ImageLine.vue` and `PileLine.vue` props/templates but is the right long-term shape — the line is data, the iterator is interaction. Selection / hover currently goes through `findImageIterator(groupId, imageId)` (line 834), which is already iterator-on-demand, so the consumers can be migrated.

### Optimisation 4.3 — Numeric line keys

```ts
id: parentGroup.id + '|img-' + groupLineIndex++
```

Allocates a string per line. With a known cap on lines per group, encode numerically:

```ts
id: parentGroup.id * 1_000_000 + groupLineIndex  // ensure no collision with group ids
```

Or maintain a global monotonic counter scoped to the current `computeLines()` call. RecycleScroller's `key-field` works fine with numbers.

### Optimisation 4.4 — Precompute parent-id chains once

`getParents` (line 280) and `getImageLineParents` walk the parent chain **per render** of each line. For thousands of visible-window updates this re-walks.

Build `group.parentIds: number[]` during `setOrder` / `buildOrdinalRanges`:

```ts
const recursive = (g: Group, parentIds: number[]) => {
    g.parentIds = parentIds
    g.order = i++
    const next = parentIds.concat(g.id)
    for (const c of g.children) recursive(c, next)
}
recursive(root, [])
```

`getParents(g)` then becomes `g.parentIds`. `getImageLineParents(item)` becomes `[...group.parentIds, item.groupId]` or just attach the same array on the image line at creation time.

### Optimisation 4.5 — Dead code

`while (imgIt && imgIt.isValid && imgIt.groupId == it.groupId && lines.length !== undefined)` — `lines.length !== undefined` is always true. Drop it.

---

## 5. Optional: chunked / async `computeLines`

For very large group counts, the synchronous compute blocks the main thread. Yield periodically:

```ts
async function computeLines() {
    const lines: ScrollerLine[] = []
    let it = props.groupManager.getGroupIterator()
    let lastYield = performance.now()
    while (it) {
        appendGroupLines(it, lines)
        it = it.nextGroup()
        if (performance.now() - lastYield > 8) {
            imageLines.value = lines.slice()  // partial render
            await new Promise(r => requestAnimationFrame(r))
            lastYield = performance.now()
        }
    }
    imageLines.value = lines
}
```

Trade-off: now `computeLines` is async; need to guard against overlapping calls (cancel token). Worth it once 1, 2, 4 are done and CPU is still the bottleneck.

---

## 6. Optional: collapse single-image groups into one line

For the "many tiny groups" worst case, every group emits 2 lines (group label + 1 image line). A new line type `'group+image'` that renders the label and the image inline halves the line count for that case. Requires a new component and a width check (skip if label needs its own row). Bigger UX change — file for later.

---

## 7. Replace `GroupValueIndex` with a hash-based stable ID

`GroupManager.ts:242` — `GroupValueIndex` builds a nested `Map<value, Map<value, ...>>` tree to assign sequential IDs to value paths. Two problems:

1. **Slow on cold paths.** Every new path allocates `k` intermediate Maps and pays `k × 2` Map ops to navigate. With many small groups, every lookup is a cold path.
2. **IDs are not deterministic across sessions** — `idCounter` resets on reload, so any persisted view state (closed/open, scroll, selection) referenced by `groupId` is invalidated.

### The replacement

A pure, stateless **53-bit hash** of the value path, with property IDs mixed in. Validated against the broken `GroupValueIndex` and several alternatives via `panoptic_front/bench_group_ids.html` on 6M unique paths:

| Approach | Cold ns/op | Hot ns/op | Collisions |
|---|---|---|---|
| A. `GroupValueIndex` (current) | 446 | 223 | 0 |
| H. **FNV+Murmur3 + string intern** | **18** | **36** | 0 |

H is **~25× faster cold** and **~6× faster hot**, with zero collisions at 6M and ~600KB of interner state (vs ~30MB of nested Maps for the current approach).

### Critical gotcha — the two streams must use *different* algebra

A naive "parallel FNV-1a" with two seeds but the **same prime** delivers only ~32 bits of entropy (we measured 1066 collisions on 3M, 4145 on 6M — matching `N²/2³³`). Both streams compute essentially the same function — different starting points don't help.

Use FNV-1a for `h1` and **Murmur3 mix** for `h2`. Verified: 0 collisions on 6M.

```ts
// In GroupManager.ts — module-level

function hashPathStrong(propIds: number[], values: any[]): number {
    let h1 = 2166136261 | 0
    let h2 = 0x9E3779B9 | 0       // Knuth golden-ratio constant
    let kk = 0
    for (let i = 0; i < values.length; i++) {
        const p = propIds[i] | 0
        // h1: FNV-1a
        h1 = Math.imul(h1 ^ p, 16777619)
        // h2: Murmur3 mix
        kk = Math.imul(p, 0xcc9e2d51); kk = (kk << 15) | (kk >>> 17); kk = Math.imul(kk, 0x1b873593)
        h2 ^= kk; h2 = (h2 << 13) | (h2 >>> 19); h2 = (Math.imul(h2, 5) + 0xe6546b64) | 0

        const v = values[i]
        const t = typeof v
        if (t === 'number') {
            const vi = v | 0
            h1 = Math.imul(h1 ^ vi, 16777619)
            kk = Math.imul(vi, 0xcc9e2d51); kk = (kk << 15) | (kk >>> 17); kk = Math.imul(kk, 0x1b873593)
            h2 ^= kk; h2 = (h2 << 13) | (h2 >>> 19); h2 = (Math.imul(h2, 5) + 0xe6546b64) | 0
        } else if (t === 'string') {
            for (let j = 0; j < v.length; j++) {
                const c = v.charCodeAt(j)
                h1 = Math.imul(h1 ^ c, 16777619)
                kk = Math.imul(c, 0xcc9e2d51); kk = (kk << 15) | (kk >>> 17); kk = Math.imul(kk, 0x1b873593)
                h2 ^= kk; h2 = (h2 << 13) | (h2 >>> 19); h2 = (Math.imul(h2, 5) + 0xe6546b64) | 0
            }
        }
        // separator
        h1 = Math.imul(h1 ^ 0xff, 16777619)
        kk = Math.imul(0xff, 0xcc9e2d51); kk = (kk << 15) | (kk >>> 17); kk = Math.imul(kk, 0x1b873593)
        h2 ^= kk; h2 = (h2 << 13) | (h2 >>> 19); h2 = (Math.imul(h2, 5) + 0xe6546b64) | 0
    }
    // Final avalanche on both streams
    h1 ^= h1 >>> 16; h1 = Math.imul(h1, 0x85ebca6b); h1 ^= h1 >>> 13
    h2 ^= h2 >>> 16; h2 = Math.imul(h2, 0xc2b2ae35); h2 ^= h2 >>> 16
    return (h1 >>> 0) * 0x200000 + (h2 >>> 11)   // 53-bit
}
```

### String interning — the second 2× win

The version above char-loops every string per call. For grouping by string/path properties with ~30k distinct values across millions of slots, you re-hash the same string thousands of times. Intern once, then the inner loop is pure numeric:

```ts
class Interner {
    private m = new Map<string, number>()
    private c = 1
    intern(s: string): number {
        let n = this.m.get(s)
        if (n === undefined) { n = this.c++; this.m.set(s, n) }
        return n
    }
}
```

Use one interner per groupBy property (or one global per `group()` run). Pass to `hashPathStrong` and replace `if (t === 'string') ...char loop...` with `v = interner.intern(v); ... mix as number`.

This is what approach H does. Net cost: one `Map.get` per string per call, vs. char-by-char hash. For ~10-char strings the breakeven is ~3 calls per string — anything more is a win, and grouping always has more.

### Integration into the codebase

1. Delete the `GroupValueIndex` class (`GroupManager.ts:242–271`).
2. Remove `valueIndex: GroupValueIndex` from `GroupTree` and `result.valueIndex = new GroupValueIndex()` from `clear()` and the constructor.
3. Remove `delete()` calls (`removeChildren` line 633, anywhere else).
4. Replace each `this.result.valueIndex.get(key)` (lines 513, 528, 652, 949) with `hashPathStrong(propIdsForKey, key)`. Thread the propIds through the call sites — `computePropertySubGroup` already has them in `groupBy`; `groupBySha1` uses `[parent propIds…, PropertyID.sha1]`.
5. Drop the `key` field's role as identity input and reuse it as the canonical path (for collision check and debugging).

### Collision safety net

Expected collision rate at 6M with true 53-bit hash: ~2×10⁻³ (i.e. 0 in 99.8% of runs). For production safety, add a one-line check in `regsiterGroup`:

```ts
private regsiterGroup(group: Group) {
    const existing = this.result.index[group.id]
    if (existing && !sameKey(existing.key, group.key)) {
        console.warn('GroupManager: hash collision', existing.key, group.key)
        // Salvage by salting: group.id = hashPathStrong([...propIds, 0xCAFE], group.key)
        // At expected rates this branch is dead code.
    }
    this.result.index[group.id] = group
}

function sameKey(a: any[], b: any[]) {
    if (a.length !== b.length) return false
    for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false
    return true
}
```

### Bonus: cross-session persistent view state

Because the ID is now a pure function of `(propIds, valuePath)`, you can persist `{ groupId → { closed: true } }` to `localStorage` and it resolves correctly after reload. Same applies to URL fragments referencing a specific group.

### Composition with other optimisations

- **§2.2 single-pass bucketing**: the hash function replaces the inner Map walk per slot in the deepest bucketing loop. The two changes are independent but stack: §2.2 cuts the number of lookups; §7 cuts the cost per lookup.
- **§2.1 `tagWithParents`** hoisting: orthogonal — still applies.

### Benchmarks for reference

Local file: `panoptic_front/bench_group_ids.html`. Open directly in a browser, configure N, click Run. Compares 8 approaches with cold/hot timings and collision counts.

---

## Suggested order

1. **Fix A or B** in §1 — kills the stack overflow. Lowest risk, highest user-facing impact.
2. **§2.1** hoist `tagWithParents` — small diff, immediate win on tag grouping.
3. **§2.4 / 2.5 / 2.6 / 4.5** — micro-opts, do them while in the file.
4. **§4.4** parent-id chains — small change, removes repeated walks.
5. **§7** hash-based stable IDs — drop-in replacement for `GroupValueIndex`. ~25× cold / ~6× hot speedup at scale, enables persistent view state. Standalone change, no template impact.
6. **§3** dirty-only iteration — moderate refactor, big win on incremental updates.
7. **§2.2** single-pass bucketing — bigger refactor, biggest win on deep multi-grouping. Composes with §7.
8. **§4.2** lazy iterators in lines — touches templates, do once §1 is shipped.
9. **§5** async compute — only if §1–§8 aren't enough.

## What I'd benchmark to validate

- `console.time('Group')` for: 3-level groupBy on a tag property with 500 tags, 100k images.
- `console.time('compute Lines')` for: same dataset + window width 300px (forces many image lines per group).
- Both should be sub-200ms after §1, §2.1, §2.2, §7.
- Stack overflow repro: large all-images group at width ~200px — should never throw after §1.
- Hash ID collision sanity: load a real dataset with 1M+ groups, count `Object.keys(result.index).length` — should equal the number of distinct paths constructed.
[]