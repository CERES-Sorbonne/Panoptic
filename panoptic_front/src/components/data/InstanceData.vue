<!-- Renderless component. Registers interest in (instanceIds × propIds) with the
     ColumnStore. The store builds and maintains the reactive instances map; this
     component just declares what it needs and cleans up on unmount.

     Usage:
       <InstanceData :instance-ids="visibleIds" :prop-ids="[namePropId, datePropId]"
                     v-slot="{ instances, selected }">
         <MyCard v-for="id in visibleIds" :key="id"
                 :name="instances[id].properties[namePropId]"
                 :selected="selected.has(id)" />
       </InstanceData>
-->
<script setup lang="ts">
defineOptions({ inheritAttrs: false })
import { reactive, getCurrentInstance, onUnmounted, watch } from 'vue'
import { useColumnStore } from '@/data/stores/columnStore'
import { useInstanceStore } from '@/data/stores/instanceStore'
import { usePanopticStore } from '@/data/stores/panopticStore'
import { useDataStore } from '@/data/stores/dataStore'

const props = defineProps<{
    instanceIds?: number[]
    propIds:      number[]
}>()

const columnStore   = useColumnStore()
const data          = useDataStore()
const instanceStore = useInstanceStore()
const panoptic      = usePanopticStore()
const uid           = String(getCurrentInstance()!.uid)

const selected = reactive(new Set<number>())

function syncSelection() {
    selected.clear()
    for (const id of (props.instanceIds ?? [])) {
        const slot = columnStore.slotMap.get(id)
        if (slot !== undefined && columnStore.isSelected(slot)) selected.add(id)
    }
}

columnStore.onSelectionChange.addListener(syncSelection)
onUnmounted(() => {
    columnStore.onSelectionChange.removeListener(syncSelection)
    instanceStore.unregister(uid)
})

// The ids `selected` was last synced for. The selection listener keeps it right for those, so a
// new array naming the same ids (a scroller rebuilding its window in place) needs no new pass.
let syncedIds: number[] = []

function sameIds(a: number[], b: number[]) {
    if (a.length !== b.length) return false
    for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false
    return true
}

watch(
    [() => props.instanceIds, () => props.propIds],
    ([ids, propIds]) => {
        if (!ids) return
        const projectId = panoptic.connectionState?.connectedProject ?? ''
        // The store skips its bookkeeping itself when this registration did not change.
        instanceStore.register(uid, ids, [...propIds, data.getSysId('width'), data.getSysId('height')], projectId)
        if (sameIds(ids, syncedIds)) return
        syncedIds = ids
        syncSelection()
    },
    { immediate: true, deep: false }
)
</script>

<template>
    <slot :instances="instanceStore.instanceData" :selected="selected" />
</template>
