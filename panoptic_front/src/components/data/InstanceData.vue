<!-- Renderless component. Fetches property values for a set of instances and
     exposes them through a slot. All instances are pre-initialized synchronously
     so instances[id].properties[propId] is always safe — no ?. needed in templates.

     Usage:
       <InstanceData :instance-ids="visibleIds" :prop-ids="[namePropId, datePropId]"
                     v-slot="{ instances, selected, loading, error }">
         <MyCard v-for="id in visibleIds" :key="id"
                 :name="instances[id].properties[namePropId]"
                 :selected="selected.has(id)" />
       </InstanceData>
-->
<script setup lang="ts">
import { ref, reactive, watch, onUnmounted } from 'vue'
import { useColumnStore } from '@/data/dataStore2'
import type { Instance } from '@/data/models'

const props = defineProps<{
    instanceIds: number[]
    propIds:     number[]
}>()

const store   = useColumnStore()
const loading = ref(false)
const error   = ref<string | null>(null)

// instances[id].properties[propId] — always defined before render (pre-initialized below)
const instances = reactive<Record<number, Instance>>({})

// Reactive Set so v-if / :class bindings on selected.has(id) update automatically
const selected = reactive<Set<number>>(new Set())

// Rebuild selected set when selection changes.
// O(instanceIds.length) per click — negligible for the ~200 items a scroll window shows.
function _syncSelection(ids: number[]) {
    selected.clear()
    for (const id of ids) {
        const slot = store.slotMap.get(id)
        if (slot !== undefined && store.isSelected(slot)) selected.add(id)
    }
}

const _onSelectionChange = () => _syncSelection(props.instanceIds)
store.onSelectionChange.addListener(_onSelectionChange)
onUnmounted(() => store.onSelectionChange.removeListener(_onSelectionChange))

watch(
    [() => props.instanceIds, () => props.propIds],
    async ([ids, propIds]) => {
        // ── Synchronous: runs before first render ──────────────────────────
        // Remove stale entries
        const newSet = new Set(ids)
        for (const id of Object.keys(instances).map(Number)) {
            if (!newSet.has(id)) delete instances[id]
        }
        // Pre-initialize every requested id so the template never sees undefined
        for (const id of ids) {
            if (!instances[id]) {
                instances[id] = { id, properties: {} } as Instance
            }
        }
        _syncSelection(ids)

        if (!ids.length || !propIds.length) return

        // ── Async: fetch missing cells, fill in place ──────────────────────
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
    { immediate: true, deep: false }
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
