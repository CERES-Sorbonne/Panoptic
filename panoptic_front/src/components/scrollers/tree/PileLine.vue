<script setup lang="ts">
import { ScrollerPileLine, Property, Sha1Scores } from '@/data/models';
import ImageVue from './Image.vue';
import { SelectedImages } from '@/core/GroupManager';
import { Ref, computed } from 'vue';


const props = defineProps<{
    imageSize: number
    inputIndex: number
    item: ScrollerPileLine
    parentIds: number[]
    hoverBorder: number
    index: any
    properties: Property[]
    selectedImages: Ref<SelectedImages>
    sha1Scores: Sha1Scores
    preview?: SelectedImages
}>()

const emits = defineEmits(['hover', 'unhover', 'scroll', 'update', 'update:selected-image'])


const selected = computed(() => {
    const res = {}
    props.item.data.forEach(it => res[it.image.id] = props.selectedImages.value[it.image.id])
    return res
})

const previews = computed(() => {
    const res = {}
    props.item.data.forEach(it => {
        if(props.preview) {
            res[it.image.id] = props.preview[it.image.id]
        }
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
            :properties="props.properties" :selected="selected[imageIt.image.id]" :selectedPreview="previews[imageIt.image.id]"
            :score="(props.sha1Scores ? props.sha1Scores[imageIt.image.sha1] : undefined)"
            @update:selected="v => emits('update:selected-image', { id: imageIt.image.id, value: v })"
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