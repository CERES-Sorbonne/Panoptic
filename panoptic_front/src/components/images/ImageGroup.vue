<script setup lang="ts">

import { computed } from 'vue'
import ExpandOption from '../menu/ExpandOption.vue';
import PaginatedImages from './PaginatedImages.vue';
import { Group, PropertyType } from '@/data/models';
import { globalStore } from '@/data/store';

const props = defineProps({
    group: Object as () => Group,
    small: String,
    imageSize: String
})

const images = computed(() => props.group.images)
const subgroups = computed(() => props.group.groups)
const hasImages = computed(() => images.value.length > 0)
const hasSubgroups = computed(() => subgroups.value != undefined)

const groupName = computed(() => {
    let name = props.group.name
    let property = globalStore.properties[props.group.propertyId]
    if(props.group.propertyId == undefined) {
        return props.group.name
    }
    if (props.group.name == "undefined") {
        name = "undefined"
    }
    else {
        let type = globalStore.properties[props.group.propertyId].type
        if (type == PropertyType.tag || type == PropertyType.multi_tags) {
            name = globalStore.tags[props.group.propertyId][Number(props.group.name)].value
        }
    }

    return property.name + ': ' + name
})

</script>

<template>
    <ExpandOption :small="props.small" :left-align="true" :reset-on-hide="true">
        <template #name>{{ groupName }} ({{ props.group.count }})<i class="h5 ms-2 bi bi-share"></i></template>
        <template #content>
            <div v-if="hasImages">
                <div class="ms-3">
                    <PaginatedImages :images="images" :image-size="imageSize" />
                </div>
            </div>
            <div v-else-if="hasSubgroups" class="ms-3">
                <ImageGroup v-for="group in subgroups" :group="group" small=true :image-size="props.imageSize" />
            </div>
            <div v-else>
                Error.. No Subgroups, No images, Why ?
            </div>
        </template>
    </ExpandOption>
</template>

<style scoped="true">
.images-group {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    grid-gap: 20px;
}

.image-card {
    height: 100%;
    max-height: 300px;
    border: 1px solid #ccc;
    padding-left: 0;
    padding-right: 0;
}

.image-card img {
    width: 100%;
    height: 100%;
    object-fit: cover;
}

.image-container {
    height: 100%;
}
</style>