<script setup lang="ts">
import { GroupIndex, Property, ScrollerLine } from '@/data/models';
import Image from './Image.vue';


const props = defineProps({
    imageSize: Number,
    inputIndex: Number,
    item: Object as () => ScrollerLine,
    parentIds: Array<string>,
    hoverBorder: String,
    index: Object as () => GroupIndex,
    properties: Array<Property>,
    selectedImages: Set<Number>
})

const emits = defineEmits(['hover', 'unhover', 'scroll', 'update', 'update:selected-image'])

</script>

<template>
    <div class="d-flex flex-row">
        <div v-for="parentId in props.parentIds" style="cursor: pointer;" class="ps-2" @click="emits('scroll', parentId)"
            @mouseenter="emits('hover', parentId)" @mouseleave="emits('unhover')">
            <div class="image-line" :class="props.hoverBorder == parentId ? 'active' : ''"></div>
        </div>
        <Image :image="image" :index="props.inputIndex + i" :groupId="item.groupId" :size="props.imageSize"
            :properties="props.properties" :selected="props.selectedImages.has(image.id)" @update:selected="v => emits('update:selected-image', {id: image.id, value:v})"
            v-for="image, i in props.item.data" class="me-2 mb-2"/>

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