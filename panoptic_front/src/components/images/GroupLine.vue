<script setup lang="ts">
import { Group, PropertyType } from '@/data/models'
import { globalStore } from '@/data/store'
import { computed } from 'vue'
import StampDropdown from '../inputs/StampDropdown.vue'
import TagBadge from '../TagTree/TagBadge.vue'


const props = defineProps({
    item: Object,
    hoverBorder: {type: Boolean, default: false}
})

const emits = defineEmits(['hover:border'])

const group = computed(() => props.item.data as Group)
const images = computed(() => props.item.data.images)
const subgroups = computed(() => props.item.data.groups)
const hasImages = computed(() => images.value.length > 0)
const hasSubgroups = computed(() => subgroups.value != undefined)
const property = computed(() => globalStore.properties[props.item.data.propertyId])

const groupName = computed(() => {
    let name = group.value.name
    if (group.value.propertyId == undefined) {
        return group.value.name
    }
    if (group.value.name == "undefined") {
        name = "undefined"
    }
    else {
        let type = globalStore.properties[group.value.propertyId].type
        if (type == PropertyType.tag || type == PropertyType.multi_tags) {
            name = globalStore.tags[group.value.propertyId][Number(group.value.name)].value
        }
    }

    return name
})

function getTag(propId: number, tagId: number) {
    return globalStore.tags[propId][tagId]
}

</script>

<template>
    <div class="d-flex flex-row">
        <div v-for="i in props.item.depth" style="cursor: pointer;" class="ps-2" @click="" @mouseenter="$emit('hover:border', true)"
            @mouseleave="$emit('hover:border', true)">
            <div class="group-line" :class="props.hoverBorder ? 'active' : ''"></div>
        </div>
        
        <div class="d-flex flex-row mb-1" ref="topElem">
                <div v-if="property != undefined && property.type != PropertyType.multi_tags && property.type != PropertyType.tag"><b>{{ property.name }}</b> : {{ groupName }}</div>
                <div v-else-if="property != undefined && (property.type == PropertyType.multi_tags || property.type == PropertyType.tag)">
                    <b>{{ property.name }}</b> : 
                    <TagBadge v-if="group.name != 'undefined'" :tag="getTag(property.id, Number(group.name)).value" :color="getTag(property.id, Number(group.name)).color" />
                    <TagBadge v-else tag="_undefined_" color="#000000" />
                </div>
                <div v-else><b>{{ groupName }}</b></div>
                <div class="ms-2">({{ group.count }})</div>
                <div v-if="hasImages && hasSubgroups" class="ms-2"><button @click="clear">Clear</button></div>
                <div v-if="hasImages && !hasSubgroups" class="ms-2">
                    <StampDropdown :images="images" />
                </div>
                <div v-if="hasImages && !hasSubgroups" class="ms-2">
                    <button @click="computeClusters">Créer clusters</button>
                </div>
                <div v-if="hasImages && !hasSubgroups" class="ms-2">
                    <input class="no-spin" type="number" v-model="props.item.data.clusterNb" style="width: 30px;" />
                </div>
                <div v-if="hasImages && !hasSubgroups" class="ms-2">
                    <button @click="recommandImages">Images Similaires</button>
                </div>
            </div>
    </div>
</template>

<style scoped>
.group-line {
    height: 100%;
    border-left: 1px solid var(--border-color);
    padding-left: 10px;
}
.active {
    border-left: 1px solid blue;
}
</style>