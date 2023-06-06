<script setup lang="ts">
import { watch } from 'vue';
import ImageVue from './Image.vue';
import ImageRecomended from './ImageRecomended.vue';
import { Group, GroupIndex, Image, PropertyType, ScrollerLine } from '@/data/models';
import { globalStore } from '@/data/store';


const props = defineProps({
    imageSize: Number,
    inputIndex: Number,
    item: Object as () => ScrollerLine,
    parentIds: Array<string>,
    hoverBorder: String,
    index: Object as () => GroupIndex
})

const emits = defineEmits(['hover', 'unhover', 'scroll', 'update'])
//:style="'padding-left:' + (props.item.depth * MARGIN) + 'px'"


function acceptRecommend(image: Image) {
    let group = props.index[props.item.groupId]
    let index = group.allSimilarSha1s.indexOf(image.sha1)
    if (index < 0) {
        return
    }

    let property = globalStore.properties[group.propertyId]
    let type = property.type

    let propertyValue: string | string[] = group.name
    if (type == PropertyType.tag || type == PropertyType.multi_tags) {
        propertyValue = [propertyValue]
    }

    globalStore.addOrUpdatePropertyToImage(image.id, property.id, propertyValue)
    

    group.allSimilarSha1s.splice(index, 1)
    emits('update', props.item.groupId)
}

function refuseRecommend(image: Image) {
    let group = props.index[props.item.groupId]
    let index = group.allSimilarSha1s.indexOf(image.sha1)
    if (index < 0) {
        return
    }

    group.allSimilarSha1s.splice(index, 1)
    group.similarSha1sBlacklist.push(image.sha1)
    emits('update', props.item.groupId)
}

</script>

<template>
    <div class="d-flex flex-row">
        <div v-for="parentId in props.parentIds" style="cursor: pointer;" class="ps-2" @click="$emit('scroll', parentId)"
            @mouseenter="$emit('hover', parentId)" @mouseleave="$emit('unhover')">
            <div class="image-line" :class="props.hoverBorder == parentId ? 'active' : ''"></div>
        </div>
        <template v-if="props.item.isSimilarities">
            <ImageRecomended :image="image" :size="props.imageSize" v-for="image, i in props.item.data"
                @accept="acceptRecommend" @refuse="refuseRecommend" />
        </template>
        <template v-else>
            <ImageVue :image="image" :index="props.inputIndex + i" :groupId="item.groupId" :size="props.imageSize"
                v-for="image, i in props.item.data" />
        </template>

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