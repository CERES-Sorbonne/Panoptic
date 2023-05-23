<script setup lang="ts">

import { computed, ref } from 'vue'
import ExpandOption from '../Menu/ExpandOption.vue';
import PaginatedImages from './PaginatedImages.vue';
import { Group, PropertyType } from '@/data/models';
import { globalStore } from '@/data/store';

const props = defineProps({
    group: Object as () => Group,
    small: String,
    imageSize: Number,
    groupId: {type: String, default: '0'}
})

const clusterNb = ref(10)

const images = computed(() => props.group.images)
const subgroups = computed(() => props.group.groups)
const hasImages = computed(() => images.value.length > 0)
const hasSubgroups = computed(() => subgroups.value != undefined)
const property = computed(() => globalStore.properties[props.group.propertyId])

const groupName = computed(() => {
    let name = props.group.name
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

    return name
})

function clear() {
    props.group.groups = undefined
}

async function computeClusters() {
    let mlGroups = await globalStore.computeMLGroups(props.group.images.map(i => i.sha1), clusterNb.value)
    props.group.groups = []
    for(let [index, group] of mlGroups.entries()){
        let realGroup: Group = {
            name: 'cluster ' + index.toString(),
            images: group,
            count:group.length,
            groups: undefined
        }
        props.group.groups.push(realGroup)
    }
}

</script>

<template>
    <ExpandOption :small="props.small" :left-align="true" :reset-on-hide="true" class="image-group">
        <template #name>
            <div class="d-flex flex-row mb-1">
                <div v-if="property != undefined"><b>{{ property.name }}</b> : {{ groupName }}</div>
                <div v-else><b>{{ groupName }}</b></div>
                <div class="ms-2">({{ props.group.count }})</div>
                <div v-if="hasImages && hasSubgroups" class="button-offset ms-2"><button @click="clear">Clear</button></div>
                <div v-if="hasImages && !hasSubgroups" class="button-offset ms-2"><button @click="computeClusters">Compute Groups</button></div>
                <div v-if="hasImages && !hasSubgroups" class="button-offset ms-2"><input class="" type="number" v-model="clusterNb" style="width: 30px;"/></div>
            </div>
             
        </template>
        <template #content>
            <div v-if="hasSubgroups" class="ms-3">
                <ImageGroup v-for="group, index in subgroups" :group="group" small=true :image-size="props.imageSize" :groupId="props.groupId + '-' + index"/>
            </div>
            <div v-else-if="hasImages">
                <div class="ms-3">
                    <PaginatedImages :images="images" :image-size="imageSize" :groupId="props.groupId"/>
                </div>
            </div>
            <div v-else>
                Error.. No Subgroups, No images, Why ?
            </div>
        </template>
    </ExpandOption>
</template>

<style scoped="true">
/* .image-group {
    border-left: 1px solid var(--border-color);
} */

.button-offset {
    position: relative;
    top: -3px
}

</style>