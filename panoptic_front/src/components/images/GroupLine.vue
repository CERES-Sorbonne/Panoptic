<script setup lang="ts">
import { Group, GroupIndex, PropertyType, ScrollerLine } from '@/data/models'
import { globalStore } from '@/data/store'
import { computed, ref } from 'vue'
import StampDropdown from '../inputs/StampDropdown.vue'
import TagBadge from '../TagTree/TagBadge.vue'


const props = defineProps({
    item: Object as () => ScrollerLine,
    parentIds: Array<string>,
    hoverBorder: String
})

const emits = defineEmits(['hover', 'unhover' ,'scroll'])

const group = computed(() => props.item.data as Group)
const images = computed(() => props.item.data.images)
const subgroups = computed(() => props.item.data.groups)
const hasImages = computed(() => images.value.length > 0)
const hasSubgroups = computed(() => subgroups.value != undefined)
const property = computed(() => globalStore.properties[props.item.data.propertyId])
const closed = computed(() => group.value?.closed)

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

function computeClusters() {

}

function clear() {

}

function recommandImages() {

}

function toggleClosed() {
    if(closed.value) {
        // props.groupIndex[props.item.id].closed = false
        props.item.data.closed = false
    }
    else {
        props.item.data.closed = true
    }
}

</script>

<template>
    <div class="d-flex flex-row group-line m-0 p-0 overflow-hidden">        
        <div v-for="parentId in props.parentIds" style="cursor: pointer;" class="ps-2" @click="$emit('scroll', parentId)" @mouseenter="$emit('hover', parentId)"
            @mouseleave="$emit('unhover')">
            <div class="group-line-border" :class="props.hoverBorder == parentId ? 'active' : ''"></div>
        </div>
        <div @click="toggleClosed" class="me-2">
            <i v-if="closed" class="bi bi-caret-right-fill" style="margin-left: 1px;"></i>
            <i v-else class="bi bi-caret-down-fill" style="margin-left: 1px;"></i>
        </div>
        <div v-if="property != undefined && property.type != PropertyType.multi_tags && property.type != PropertyType.tag">
            <b>{{ property.name }}</b> : {{ groupName }}
        </div>
        <div
            v-else-if="property != undefined && (property.type == PropertyType.multi_tags || property.type == PropertyType.tag)">
            <b>{{ property.name }}</b> :
            <TagBadge v-if="!isNaN(Number(group.name))" :tag="getTag(property.id, Number(group.name)).value"
                :color="getTag(property.id, Number(group.name)).color" />
            <TagBadge v-else tag="_undefined_" color="#000000" />
        </div>
        <div v-else><b>{{ groupName }}</b></div>
        <div class="ms-2 text-secondary" style="font-size: 11px; line-height: 25px;">{{ group.count }} Images</div>
        <div v-if="group.groups" class="ms-2 text-secondary" style="font-size: 11px; line-height: 25px;">{{ group.groups.length }} Groupes</div>
        <div v-if="hasImages && hasSubgroups" class="ms-2" ><button @click="clear">Clear</button></div>
        <div v-if="hasImages && !hasSubgroups" class="ms-2">
            <StampDropdown :images="images" />
        </div>
        <div class="ms-2" v-if="!hasSubgroups">
            <!-- <button @click="computeClusters">Créer clusters</button> -->
            <div class="button">Créer clusters</div>
        </div>
        <div v-if="hasImages && !hasSubgroups" style="margin-left: 2px;">
            <input class="no-spin" type="number" v-model="props.item.nbClusters" style="width: 30px;" />
        </div>
        <div v-if="hasImages && !hasSubgroups" class="ms-2">
            <div class="button" @click="recommandImages">Images Similaires</div>
        </div>
    </div>
</template>

<style scoped>
.group-line {
    /* position: relative; */
    height: 30px;
    /* line-height: 25px; */
}

.group-line-border {
    height: 100%;
    border-left: 1px solid var(--border-color);
    padding-left: 10px;
}

.active {
    border-left: 1px solid blue;
}
</style>