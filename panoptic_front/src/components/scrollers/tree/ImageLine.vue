<script setup lang="ts">
import ImageVue from '@/components/images/Image.vue';
import ImageUnique from '@/components/images/ImageUnique.vue';
import { GroupIndex, Property, ScrollerLine } from '@/data/models';


const props = defineProps({
    imageSize: Number,
    inputIndex: Number,
    item: Object as () => ScrollerLine,
    parentIds: Array<string>,
    hoverBorder: String,
    index: Object as () => GroupIndex,
    properties: Array<Property>
})

const emits = defineEmits(['hover', 'unhover', 'scroll', 'update'])
//:style="'padding-left:' + (props.item.depth * MARGIN) + 'px'"

</script>

<template>
    <div class="d-flex flex-row">
        <div v-for="parentId in props.parentIds" style="cursor: pointer;" class="ps-2" @click="emits('scroll', parentId)"
            @mouseenter="emits('hover', parentId)" @mouseleave="emits('unhover')">
            <div class="image-line" :class="props.hoverBorder == parentId ? 'active' : ''"></div>
        </div>
        <ImageUnique :image="image" :index="props.inputIndex + i" :groupId="item.groupId" :size="props.imageSize"
            :properties="props.properties"
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