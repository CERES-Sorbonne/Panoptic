# New DataStore Design — Decoupled Reactivity & Columnar Performance Layer

## Goal

At 1M images the current dataStore conflates two concerns that have opposite requirements:

- **UI reactivity** — deep Vue reactive objects, fine-grained updates, small working set
- **Computation** — cache-friendly typed arrays, zero GC pressure, no Vue overhead

The new design separates these into two parallel stores that share no reactive state and synchronise explicitly. During migration the new store runs **in parallel** with the existing `Instance.properties` dict and is connected progressively.

---

## What is always loaded vs. lazy

**Always loaded eagerly:**

| Data | Why |
|---|---|
| Instance IDs + slot map | Foundation for every operation |
| Instance metadata (sha1, folderId, width, height) | Thumbnails, folder filter, dimensions |
| Folder index | Default folder filter UI |
| Properties list (name, type, mode) | Property panel, filter/sort/group UI |
| Tags (id, value, parents, allChildren) | Tag filter UI, tag display |

**Lazy — all property values.** Two consumer paths, one shared cache:

- **UI path** (`<InstanceData>`) — fetches values for a small subset of instances on demand
- **Computation path** (`CollectionManager`) — fetches full columns for filter/sort/group

---

## Two-Layer Architecture

```
Backend stream
  ├── eager: metadata, folders, properties, tags ──────────────► always in memory
  └── lazy:  property values                                      fetched on demand
                                                                       │
                                                         ┌─────────────▼──────────────┐
                                                         │   COLUMN STORE             │
                                                         │   (non-reactive)           │
                                                         │                            │
                                                         │  slot map  id → slot       │
                                                         │  metadata columns          │
                                                         │  property columns (sparse) │
                                                         │  fetched bitmask per prop  │
                                                         │  selectionMask: Uint8Array │
                                                         │  tag sparse + CSR          │
                                                         │  EventEmitter (changes)    │
                                                         └─────────────┬──────────────┘
                                                                       │
                         UI component ◄─── slot data ─── requireInstanceValues(ids, propIds)
                         CollectionManager ◄──────────── requireFullColumn(propId)
```

---

## Column Store

### Slot management (always built)

```ts
slotMap:     Map<instanceId, slot>   // id → slot
slotToId:    Int32Array              // slot → id
slotCount:   number
deletedMask: Uint8Array              // 1 = deleted, excluded from computations
```

Slots are append-only. Deleted instances keep their slot.

### Metadata columns (always built)

```ts
sha1Column:    string[]
folderColumn:  Int32Array
widthColumn:   Int32Array
heightColumn:  Int32Array
```

### Property value columns — cell-level cache

```ts
// Non-reactive typed arrays. Never touched by Vue.
const columnData: Record<propId, ColumnData> = {}

type ColumnData =
    | { kind: 'numeric'; data: Float64Array }         // number, date (epoch ms), color
    | { kind: 'bool';    data: Uint8Array }            // checkbox — 0/1/255=unset
    | { kind: 'string';  data: (string | null)[] }    // text, path, url, ahash
    | { kind: 'tag';     sparse: (number[] | null)[]  // partial fetch path (UI)
                         csr?: { offsets: Int32Array, values: Int32Array } } // full column path

// Which slots have been populated. 0 = not fetched, 1 = fetched (even if value is null).
const columnFetched: Record<propId, Uint8Array> = {}

// Reactive: full-column status only. Small, cheap for Vue to observe.
const fullColumnStatus = reactive<Record<propId, 'empty' | 'loading' | 'loaded'>>({})
```

### Tag columns — two-level structure

Tags use a hybrid approach because CSR is incompatible with partial slot fills:

- **`sparse`** — `(number[] | null)[]` indexed by slot. Used for UI fetches and incremental updates. Any slot can be filled independently in any order. `null` = not yet fetched.
- **`csr`** — built once when `requireFullColumn` resolves. Used exclusively by CollectionManager for cache-friendly full sequential scans (filter/group over all 1M instances).

**Why CSR cannot be used for the UI path:** CSR requires all slot tag-counts before `offsets` can be computed. Cell-level fetches arrive in arbitrary slot order so `offsets[i]` cannot be determined until all preceding slots are known. `sparse` has no such constraint.

### Tag update and incremental computation strategy

When a commit arrives changing tags for K instances, the path taken depends on K relative to a threshold (~1% of slotCount ≈ 10k):

**K ≤ threshold — incremental path (no CSR rebuild):**

1. Update `sparse[slot]` for each dirty slot — O(K), essentially free.
2. Emit `onChange({ propIds, instanceIds })`.
3. CollectionManager calls `updateSelection(dirtyIds)` on each manager, reading from `sparse[slot]` directly for the dirty slots.

Reading `sparse[slot]` vs CSR for K dirty instances has **no measurable performance difference** — the CSR's cache advantage only emerges at full-scan scale (K ≈ n). For K = 5–10k, both are O(K) with negligible constants.

The managers already implement this path:
```ts
columnStore.onChange.on(({ propIds, instanceIds }) => {
    if (dirtyCount <= INCREMENTAL_THRESHOLD) {
        // sparse[slot] read for dirty slots only — fast, no rebuild
        filterManager.updateSelection(dirty, removed)   // O(K × filterOps)
        sortManager.updateSelection(dirty, removed)     // O(K log n)
        groupManager.updateSelection(dirty, removed)    // O(K × groupDepth)
    } else {
        triggerFullRecompute(propIds)
    }
})
```

**K > threshold — full recompute path:**

1. Update `sparse[slot]` for all K dirty slots — O(K).
2. Mark `csr` as stale (`fullColumnStatus[propId] = 'loading'`).
3. Rebuild CSR from `sparse` in one sequential pass — O(n), ~10–30 ms.
4. Run full filter/sort/group — O(n).

Steps 3–4 can be done in a Web Worker to avoid main-thread blocking.

**CSR rebuild cost for reference:** one pass over 1M slots reading `sparse` + writing two `Int32Array` (~12 MB total). The bottleneck is the 1M pointer dereferences into the sparse JS array (~10–30 ms on main thread, ~3–8 ms in a Worker with less GC pressure).

### Selection (non-reactive)

```ts
const selectionMask: Uint8Array   // slot → 0/1. Not reactive.
const onSelectionChange = new EventEmitter()
```

Selection is never put into Vue reactivity. Components that need to display selection state subscribe to `onSelectionChange` and read `selectionMask` directly for their specific slots.

### Change emitter

```ts
const onChange = new EventEmitter()
// Emitted after any cell update (commit, undo, plugin write).
// Payload: { propIds: number[], instanceIds: number[] }
// CollectionManager subscribes and re-runs incrementally.
```

This replaces the existing `dirtyInstances` pattern for the new store. The ColumnStore owns the notification — callers do not need to track dirty state themselves.

### Store API

```ts
// UI path — targeted fetch for a subset of instances.
// First call for a given component is fired immediately.
// Subsequent calls within the debounce window are batched with all other
// active components' pending requests into one combined API call.
async function requireInstanceValues(
    instanceIds: number[],
    propIds:     number[]
): Promise<Map<instanceId, Record<propId, any>>>

// Computation path — fetches the entire column unconditionally.
// Always does a full fetch regardless of how many slots are already in cache
// (partial pre-fetched slots are a negligible fraction of 1M).
// Builds CSR for tag columns after the fetch completes.
async function requireFullColumn(propId: number): Promise<void>
async function requireTagInverted(propId: number): Promise<void>

// Synchronous reads — call only after require* has resolved.
function readSlot(propId: number, slot: number): any
function isFetched(propId: number, slot: number): boolean
function isSelected(slot: number): boolean

// Selection mutations — update selectionMask and emit onSelectionChange.
function select(slots: number[]): void
function deselect(slots: number[]): void
function clearSelection(): void
```

### Backend API endpoint (new, to be added)

```
GET /instances/values?ids=1,2,3&propIds=3,5
```

Returns property values for a specific subset of instances and properties:

```json
{
  "1": { "3": "some text", "5": 42.0 },
  "2": { "3": null,        "5": 7.0  },
  "3": { "3": "hello",     "5": null }
}
```

The existing stream format (`InstanceValuesArray`) is kept for the initial load. This new endpoint is only for on-demand subset fetches.

---

## Vue Component — `<InstanceData>`

Renderless wrapper. Requests data for a list of instances + properties, fires the store fetch, and exposes a reactive `instances` object through the slot.

### Why `reactive()` over `shallowRef`

Using `reactive()` with pre-initialization lets the template write `instances[id].properties[propId]` without `?.` optional chaining, and gives fine-grained cell-level updates — only the cells that actually changed re-render, not the entire scroll window.

The trick: the synchronous part of the watch (before the first `await`) initializes `instances[id]` for every requested ID before Vue renders. So `instances[id]` is always defined.

```vue
<!-- src/components/data/InstanceData.vue -->
<script setup lang="ts">
import { ref, reactive, watch, onUnmounted } from 'vue'
import { useColumnStore } from '@/data/columnStore'
import type { Instance } from '@/data/models'

const props = defineProps<{
    instanceIds: number[]
    propIds:     number[]
}>()

const store   = useColumnStore()
const loading = ref(false)
const error   = ref<string | null>(null)
const selected = reactive<Set<number>>(new Set())

// instances[id].properties[propId] — always safe, no ?. needed
const instances = reactive<Record<number, Instance>>({})

// Rebuild selected set from selectionMask when selection changes.
// Acceptable cost: O(instanceIds.length) per click — negligible for ~200 items.
const unsub = store.onSelectionChange.on(() => {
    selected.clear()
    for (const id of props.instanceIds) {
        const slot = store.slotMap.get(id)
        if (slot !== undefined && store.isSelected(slot)) selected.add(id)
    }
})
onUnmounted(unsub)

watch(
    [() => props.instanceIds, () => props.propIds],
    async ([ids, propIds]) => {
        // --- Synchronous: runs before first render ---
        // Remove stale IDs
        const newSet = new Set(ids)
        for (const id of Object.keys(instances).map(Number)) {
            if (!newSet.has(id)) delete instances[id]
        }
        // Pre-initialize so instances[id] is always defined in the template
        for (const id of ids) {
            if (!instances[id]) instances[id] = { id, properties: {} } as Instance
        }
        // Sync selection state for new IDs
        selected.clear()
        for (const id of ids) {
            const slot = store.slotMap.get(id)
            if (slot !== undefined && store.isSelected(slot)) selected.add(id)
        }

        if (!ids.length || !propIds.length) return

        // --- Async: fetch and fill ---
        loading.value = true
        error.value   = null
        try {
            const result = await store.requireInstanceValues(ids, propIds)
            // Vue tracks each assignment individually — only changed cells re-render
            for (const [id, values] of result) {
                for (const [propId, value] of Object.entries(values)) {
                    instances[id].properties[Number(propId)] = value
                }
            }
        } catch (e) {
            error.value = String(e)
        } finally {
            loading.value = false
        }
    },
    { immediate: true }
)
</script>

<template>
    <slot
        :instances="instances"
        :selected="selected"
        :loading="loading"
        :error="error"
    />
</template>
```

### Slot signature

```ts
{
    instances: Record<instanceId, Instance>   // instances[id].properties[propId]
    selected:  Set<instanceId>                // which of the requested ids are selected
    loading:   boolean
    error:     string | null
}
```

`instances[id].properties[propId]` is always safe — the structure is pre-initialized synchronously. If a property has no value, `properties[propId]` is `undefined`, which Vue renders as an empty string with no error.

`ready` is dropped — `loading` is sufficient. The instances object is always present and fills in as data arrives; there is no blank state to guard against.

### Request batching in the store

When multiple `<InstanceData>` components are mounted simultaneously (e.g. scroll window + open panel), they each call `requireInstanceValues`. The store accumulates all pending `(instanceId, propId)` requests within one microtask tick and fires a single combined API call. The first invocation per component triggers immediately; subsequent calls within a debounce window are merged with all other active pending requests.

```
tick 0: ImageGrid calls requireInstanceValues([100..299], [3,5])  → fires immediately
tick 0: DetailPanel calls requireInstanceValues([42], [3,5,8,9])  → merged into same call
         → one API call: ids=[42,100..299], propIds=[3,5,8,9]

scroll event:
tick 1: ImageGrid calls requireInstanceValues([110..309], [3,5])  → debounced
tick 1: (debounce window) → fires: ids=[110..309], propIds=[3,5]
```

### Usage examples

**Visible scroll window:**
```vue
<InstanceData :instance-ids="visibleIds" :prop-ids="[datePropId, namePropId]"
              v-slot="{ instances, selected, loading }">
    <ImageCard
        v-for="id in visibleIds" :key="id"
        :name="instances[id].properties[namePropId]"
        :date="instances[id].properties[datePropId]"
        :selected="selected.has(id)"
        :loading="loading"
    />
</InstanceData>
```

**Detail panel — all properties for one image:**
```vue
<InstanceData :instance-ids="[image.id]" :prop-ids="allPropIds" v-slot="{ instances, loading }">
    <PropertyList :values="instances[image.id].properties" :loading="loading" />
</InstanceData>
```

**Metadata-only (thumbnails, no property values):**
```vue
<!-- propIds=[] → skips fetch, instances pre-initialized with empty properties -->
<InstanceData :instance-ids="visibleIds" :prop-ids="[]" v-slot="{ instances, selected }">
    <ThumbnailGrid :ids="visibleIds" :selected="selected" />
</InstanceData>
```

---

## How CollectionManager integrates

**Initial run / state change** — CollectionManager fetches full columns, then scans typed arrays with no Vue involvement:

```ts
async function runFilter(state: FilterState) {
    const propIds = extractPropertyIds(state.filter)
    await Promise.all(propIds.map(id => columnStore.requireFullColumn(id)))

    // Pure typed array scan — no Vue, no GC, no object allocation
    for (let slot = 0; slot < columnStore.slotCount; slot++) {
        if (columnStore.deletedMask[slot]) continue
        // evaluate filter against columnData[propId]
        // for tag props: use csr (offsets + values) — sequential, cache-friendly
    }
}
```

**After a commit** — CollectionManager subscribes to `columnStore.onChange` and chooses path based on dirty count:

```ts
columnStore.onChange.on(({ propIds, instanceIds }) => {
    const relevant = propIds.some(id => activeProps.has(id))
    if (!relevant) return

    if (instanceIds.length <= INCREMENTAL_THRESHOLD) {
        // Reads sparse[slot] for dirty slots — no CSR needed, no rebuild
        const dirty = new Set(instanceIds)
        const removed = dirty  // re-evaluated below by each manager
        filterManager.updateSelection(dirty, removed)
        sortManager.updateSelection(dirty, removed)
        groupManager.updateSelection(dirty, removed)
    } else {
        // Full recompute — requireFullColumn rebuilds CSR before scan
        runFullRecompute(propIds)
    }
})
```

---

## Constants

Two values that are easy to change and may need tuning:

```ts
// Debounce window for requireInstanceValues after the first immediate call.
// All active <InstanceData> components' requests are merged within this window.
const INSTANCE_VALUES_DEBOUNCE_MS = 50

// Below this dirty count, use incremental updateSelection() with sparse reads.
// Above it, rebuild CSR and run full recompute.
const INCREMENTAL_UPDATE_THRESHOLD = 10_000   // ~1% of 1M
```