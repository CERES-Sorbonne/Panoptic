<script setup lang="ts">
import { ScrollerPileLine, Property, Sha1Scores } from '@/data/models';
import ImageVue from './Image.vue';
import { SelectedImages } from '@/core/GroupManager';


const props = defineProps({
    imageSize: Number,
    inputIndex: Number,
    item: Object as () => ScrollerPileLine,
    parentIds: Array<string>,
    hoverBorder: String,
    index: Object,
    properties: Array<Property>,
    selectedImages: Object as () => SelectedImages,
    sha1Scores: Object as () => Sha1Scores
})

const emits = defineEmits(['hover', 'unhover', 'scroll', 'update', 'update:selected-image'])

</script>

<template>
    <div class="d-flex flex-row">
        <div v-for="parentId in props.parentIds" style="cursor: pointer;" class="ps-2" @click="emits('scroll', parentId)"
            @mouseenter="emits('hover', parentId)" @mouseleave="emits('unhover')">
            <div class="image-line" :class="props.hoverBorder == parentId ? 'active' : ''"></div>
        </div>
        <ImageVue :group="group" :index="props.inputIndex + i" :groupId="item.groupId" :size="props.imageSize"
            :properties="props.properties" :selected="props.selectedImages[group.images[0].id]" :score="(props.sha1Scores ? props.sha1Scores[group.images[0].sha1] : undefined)"
            @update:selected="v => emits('update:selected-image', { id: group.images[0].id, value: v })"
            v-for="group, i in props.item.data" class="me-2 mb-2" />

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