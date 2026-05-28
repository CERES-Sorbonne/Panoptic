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
import { useColumnStore } from '@/data/dataStore2'

const props = defineProps<{
    instanceIds?: number[]
    propIds:      number[]
}>()

const store = useColumnStore()
const uid   = String(getCurrentInstance()!.uid)

const selected = reactive(new Set<number>())

function syncSelection() {
    selected.clear()
    for (const id of (props.instanceIds ?? [])) {
        const slot = store.slotMap.get(id)
        if (slot !== undefined && store.isSelected(slot)) selected.add(id)
    }
}

store.onSelectionChange.addListener(syncSelection)
onUnmounted(() => {
    store.onSelectionChange.removeListener(syncSelection)
    store.unregister(uid)
})

watch(
    [() => props.instanceIds, () => props.propIds],
    ([ids, propIds]) => {
        if (!ids) return
        store.register(uid, ids, propIds)
        syncSelection()
    },
    { immediate: true, deep: false }
)
</script>

<template>
    <slot :instances="store.instances" :selected="selected" />
</template>
