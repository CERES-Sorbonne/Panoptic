<script setup lang="ts">
import { ScrollerLine, Property, ImageLine } from '@/data/models';
import Image from './Image.vue';
import { GroupIndex, SelectedImages } from '@/core/GroupManager';
import { Ref, computed } from 'vue';


const props = defineProps<{
    imageSize: number,
    inputIndex: number,
    item: ImageLine,
    parentIds: number[],
    hoverBorder: number,
    index: GroupIndex,
    properties: Property[],
    selectedImages: Ref<SelectedImages>,
    preview?: Ref<SelectedImages>,
}>()

const emits = defineEmits(['hover', 'unhover', 'scroll', 'update', 'update:selected-image'])

const selected = computed(() => {
    const res = {}
    props.item.data.forEach(it => res[it.image.id] = props.selectedImages.value[it.image.id])
    return res
})

const preview = computed(() => {
    const res = {}
    props.item.data.forEach(it => res[it.image.id] = props.preview?.value[it.image.id])
    return res
})

</script>

<template>
    <div class="d-flex flex-row">
        <div v-for="parentId in props.parentIds" style="cursor: pointer;" class="ps-2"
            @click="emits('scroll', parentId)" @mouseenter="emits('hover', parentId)" @mouseleave="emits('unhover')">
            <div class="image-line" :class="props.hoverBorder == parentId ? 'active' : ''"></div>
        </div>
        <Image :image="imageIt" :index="props.inputIndex + i" :groupId="item.groupId" :size="props.imageSize"
            :properties="props.properties" :selected="selected[imageIt.image.id]" :selectedPreview="preview[imageIt.image.id]"
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