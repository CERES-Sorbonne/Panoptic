<script setup lang="ts">
import { ScrollerPileLine, Property, Sha1Scores } from '@/data/models';
import ImageVue from './Image.vue';
import { SelectedImages } from '@/core/GroupManager';
import { useColumnStore } from '@/data/columnStore';
import { Ref, computed } from 'vue';

const col = useColumnStore()

const props = defineProps<{
    imageSize: number
    inputIndex: number
    item: ScrollerPileLine
    parentIds: number[]
    hoverBorder: number
    index: any
    properties: Property[]
    sha1Scores: Sha1Scores
    preview?: SelectedImages
}>()

const emits = defineEmits(['hover', 'unhover', 'scroll', 'update', 'update:selected-image'])


const selected = computed(() => {
    col.selectionVersion.value  // reactive dep on global selection (step 2)
    const res = {}
    const ids = col.instanceIds()
    props.item.data.forEach(it => {
        const id = ids[it.slot]
        res[id] = col.isSelected(it.slot)
    })
    return res
})

const previews = computed(() => {
    const res = {}
    if (!props.preview) return res
    const ids = col.instanceIds()
    props.item.data.forEach(it => {
        const id = ids[it.slot]
        res[id] = props.preview[id]
    })
    return res
})

</script>

<template>
    <div class="d-flex flex-row">
        <div v-for="parentId in props.parentIds" style="cursor: pointer;" class="ps-2"
            @click="emits('scroll', parentId)" @mouseenter="emits('hover', parentId)" @mouseleave="emits('unhover')">
            <div class="image-line" :class="props.hoverBorder == parentId ? 'active' : ''"></div>
        </div>
        <ImageVue :image="imageIt" :index="props.inputIndex + i" :groupId="item.groupId" :size="props.imageSize"
            :properties="props.properties" :selected="selected[col.instanceIds()[imageIt.slot]]" :selectedPreview="previews[col.instanceIds()[imageIt.slot]]"
            @update:selected="v => emits('update:selected-image', { id: col.instanceIds()[imageIt.slot], value: v })"
            v-for="imageIt, i in props.item.data" class="me-2 mb-2" />

    </div>
</template>

<style scoped>
.image-line {
    height: 100%;
    border-left: 1px solid var(--border-color);
    padding-left: 10px;
}

.active {
    border-left: 1px solid blue;
}
</style>