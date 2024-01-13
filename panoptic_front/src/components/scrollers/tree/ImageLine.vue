<script setup lang="ts">
import { ScrollerLine, Property, ImageLine } from '@/data/models';
import Image from './Image.vue';
import { GroupIndex, SelectedImages } from '@/core/GroupManager';


const props = defineProps<{
    imageSize: number,
    inputIndex: number,
    item: ImageLine,
    parentIds: string[],
    hoverBorder: string,
    index: GroupIndex,
    properties: Property[],
    selectedImages: SelectedImages
}>()

const emits = defineEmits(['hover', 'unhover', 'scroll', 'update', 'update:selected-image'])

</script>

<template>
    <div class="d-flex flex-row">
        <div v-for="parentId in props.parentIds" style="cursor: pointer;" class="ps-2" @click="emits('scroll', parentId)"
            @mouseenter="emits('hover', parentId)" @mouseleave="emits('unhover')">
            <div class="image-line" :class="props.hoverBorder == parentId ? 'active' : ''"></div>
        </div>
        <Image :image="imageIt" :index="props.inputIndex + i" :groupId="item.groupId" :size="props.imageSize"
            :properties="props.properties" :selected="props.selectedImages[imageIt.image.id] == true" @update:selected="v => emits('update:selected-image', {id: imageIt.image.id, value:v})"
            v-for="imageIt, i in props.item.data" class="me-2 mb-2"/>

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