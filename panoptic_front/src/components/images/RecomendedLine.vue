<script setup lang="ts">
import { computed } from 'vue'
import { globalStore } from '@/data/store';
import { Image, Modals, RecomendedLine } from '@/data/models';

// const props = defineProps({
//     image: Object as () => Image,
//     size: { type: Number, default: 100 },
//     callback: {type: Function},
//     refuse: {type: Function}
// })

const props = defineProps({
    imageSize: Number,
    index: Number,
    item: Object as () => RecomendedLine,
    parentIds: Array<string>,
    hoverBorder: String
})

const emits = defineEmits(['hover', 'unhover' ,'scroll'])
//:style="'padding-left:' + (props.item.depth * MARGIN) + 'px'"
</script>

<template>
    <div class="d-flex flex-row">
        <div v-for="parentId in props.parentIds" style="cursor: pointer;" class="ps-2" @click="$emit('scroll', parentId)" @mouseenter="$emit('hover', parentId)"
            @mouseleave="$emit('unhover')">
            <div class="image-line" :class="props.hoverBorder == parentId ? 'active' : ''"></div>
        </div>
        <Image :image="image" :index="props.index + i" :groupId="item.groupId" :size="props.imageSize"
            v-for="image, i in props.item.data" />
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