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
import { useColumnStore } from '@/data/columnStore'
import { useInstanceStore } from '@/data/instanceStore'
import { usePanopticStore } from '@/data/panopticStore'
import { useDataStore } from '@/data/dataStore'

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

watch(
    [() => props.instanceIds, () => props.propIds],
    ([ids, propIds]) => {
        if (!ids) return
        const projectId = panoptic.connectionState?.connectedProject ?? ''
        instanceStore.register(uid, ids, [...propIds, data.getSysId('width'), data.getSysId('height')], projectId)
        syncSelection()
    },
    { immediate: true, deep: false }
)
</script>

<template>
    <slot :instances="instanceStore.instanceData" :selected="selected" />
</template>
