<script setup lang="ts">
import { GroupManager } from '@/core/GroupManager';
import { Instance, Property } from '@/data/models';
import { defineProps, defineEmits, onMounted, watch, ref, nextTick } from 'vue'
import TreeScroller from '@/components/scrollers/tree/TreeScroller.vue';

const props = defineProps<{
    instances: Instance[]
    properties?: Property[]
}>()
// const emits = defineEmits([])

const groupManager = new GroupManager()
const box = ref(null)
const scroller = ref(null)

const height = ref(0)
const width = ref(0)

function update() {
    console.log('setup')
    groupManager.group(props.instances)

    width.value = box.value.offsetWidth
    height.value = box.value.offsetHeight
    console.log(width.value, height.value)

    nextTick(() => scroller.value.computeLines())
}

onMounted(update)
watch(() => props.instances, update)

</script>

<template>
    <div style="height: 100%; width: 100%;" ref="box">
        <TreeScroller :group-manager="groupManager" :image-size="100" :height="height" :width="width -20"
            :properties="props.properties ?? []" ref="scroller" :hide-group="true"/>
    </div>
</template>

<style scoped></style>