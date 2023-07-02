<script setup lang="ts">
import ImageVue from './Image.vue';
import { GroupIndex, ScrollerPileLine } from '@/data/models';
import Pile from './Pile.vue';


const props = defineProps({
    imageSize: Number,
    inputIndex: Number,
    item: Object as () => ScrollerPileLine,
    parentIds: Array<string>,
    hoverBorder: String,
    index: Object as () => GroupIndex
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
        <Pile :pile="pile" :index="props.inputIndex + i" :groupId="item.groupId" :size="props.imageSize"
            v-for="pile, i in props.item.data" />

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