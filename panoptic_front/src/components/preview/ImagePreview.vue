<script setup lang="ts">
import { GroupManager } from '@/core/GroupManager';
import { Property } from '@/data/models';
import { useColumnStore } from '@/data/columnStore';
import { onMounted, watch, ref, nextTick } from 'vue'
import TreeScroller from '@/components/scrollers/tree/TreeScroller.vue';

const columnStore = useColumnStore()

const props = defineProps<{
    instanceIds: number[]
    properties?: Property[]
}>()

const groupManager = new GroupManager()
const box = ref(null)
const scroller = ref(null)

const height = ref(0)
const width = ref(0)

async function update() {
    const slots = new Int32Array(props.instanceIds.length)
    let len = 0
    for (const id of props.instanceIds) {
        const slot = columnStore.slotMap.get(id)
        if (slot !== undefined) slots[len++] = slot
    }
    await groupManager.group(slots.subarray(0, len))

    width.value = box.value.offsetWidth
    height.value = box.value.offsetHeight

    nextTick(() => scroller.value.computeLines())
}

onMounted(update)
watch(() => props.instanceIds, update)

</script>

<template>
    <div style="height: 100%; width: 100%;" ref="box">
        <TreeScroller input-key="preview-scroller" :group-manager="groupManager" :image-size="100" :height="height" :width="width - 20"
            :properties="props.properties ?? []" ref="scroller" :hide-group="true" />
    </div>
</template>

<style scoped></style>