<script setup lang="ts">
import { Group, GroupLine, PropertyType, ScrollerLine } from '@/data/models'
import { globalStore } from '@/data/store'
import { computed, ref, unref } from 'vue'
import StampDropdown from '@/components/inputs/StampDropdown.vue'
import { UNDEFINED_KEY } from '@/utils/groups'
import PropertyValue from '@/components/properties/PropertyValue.vue'
import SelectCircle from '@/components/inputs/SelectCircle.vue'


const props = defineProps({
    item: Object as () => GroupLine,
    parentIds: Array<string>,
    hoverBorder: String,
    index: Object as () => { [id: string]: Group },
    hideOptions: Boolean
})

const emits = defineEmits(['hover', 'unhover', 'scroll', 'group:close', 'group:open', 'group:update', 'recommend'])

const hoverGroup = ref(false)

const group = computed(() => props.item.data as Group)
const images = computed(() => props.item.data.images)
const piles = computed(() => props.item.data.imagePiles)
const subgroups = computed(() => props.item.data.groups)
const hasImages = computed(() => images.value.length > 0)
const hasPiles = computed(() => Array.isArray(piles.value))
const hasSubgroups = computed(() => subgroups.value != undefined)
const property = computed(() => globalStore.properties[props.item.data.propertyId])
const closed = computed(() => group.value?.closed)
const hasOpenChildren = computed(() => group.value.groups.some(g => g.closed != true))


const groupName = computed(() => {
    let name = group.value.name
    if (group.value.propertyId == undefined) {
        return group.value.name
    }
    else if (group.value.name == "undefined") {
        name = "undefined"
    }
    else {
        let type = globalStore.properties[group.value.propertyId].type
        if (type == PropertyType.tag || type == PropertyType.multi_tags) {
            name = globalStore.tags[group.value.propertyId][Number(group.value.name)].value
        } else if (type == PropertyType._folders) {
            name = globalStore.folders[Number(group.value.name)].name
        }
    }

    return name
})

const someValue = computed(() => props.item.data.propertyValues.some(v => v.value != UNDEFINED_KEY))

function getTag(propId: number, tagId: number) {
    return globalStore.tags[propId][tagId]
}

async function computeClusters() {
    let sha1s: string[] = []
    if(hasPiles.value) {
        sha1s = group.value.imagePiles.map(p => p.sha1)
    }
    else if (hasImages.value) {
        sha1s = [...new Set(group.value.images.map(i => i.sha1))]
    }
    let mlGroups = await globalStore.computeMLGroups(sha1s, props.item.nbClusters)
    let distances = mlGroups.distances
    mlGroups = mlGroups.clusters
    // props.item.data.groups = []

    let groups = []
    for (let [index, sha1s] of mlGroups.entries()) {
        let images = globalStore.getOneImagePerSha1(sha1s)
        let piles = sha1s.map((s:string) => ({sha1: s, images: globalStore.sha1Index[s]})) 
        let realGroup: Group = {
            id: props.item.id + '-cluster' + String(index),
            name: 'cluster ' + index.toString() + (distances.length > 0 ? ' ' + distances[index].toString() : ''),
            images: [],
            imagePiles: piles,
            count: sha1s.length,
            groups: undefined,
            children: undefined,
            parentId: props.item.data.id,
            propertyValues: props.item.data.propertyValues,
            index: index,
            depth: (props.item.data.depth + 1),
            closed: false,
            isCluster: true
        }
        groups.push(realGroup)
        props.index[realGroup.id] = realGroup
    }
    props.item.data.groups = groups
    props.item.data.children = groups.map(g => g.id)
    emits('group:update')
}

function clear() {
    delete props.item.data.groups
    delete props.item.data.allSimilarSha1s
    delete props.item.data.similarSha1sBlacklist
    emits('group:update')
}

async function recommandImages() {
    let sha1s: string[] = []
    if(hasPiles.value) {
        sha1s = group.value.imagePiles.map(p => p.sha1)
    }
    else if (hasImages.value) {
        sha1s = [...new Set(group.value.images.map(i => i.sha1))]
    }
    // let sha1s = {} as any
    // group.value.images.forEach(i => sha1s[i.sha1] = true)

    let res = await globalStore.getSimilarImages(sha1s) as any[]
    let resSha1s = res.map(r => r.sha1)

    const propertyValues = props.item.data.propertyValues.map(unref)

    emits('recommend', resSha1s, propertyValues, props.item.data.id)


    // if (!Array.isArray(props.item.data.similarSha1sBlacklist)) {
    //     props.item.data.similarSha1sBlacklist = []
    // }

    // let all = props.item.data.allSimilarSha1s
    // let blacklist = props.item.data.similarSha1sBlacklist

    // props.item.data.getSimilarImages = () => globalStore.getOneImagePerSha1(all.filter(sha1 => !blacklist.includes(sha1)).slice(0, 30))

    // emits('group:update')
}

function toggleClosed() {
    if (closed.value) {
        // props.groupIndex[props.item.id].closed = false
        props.item.data.closed = false
        emits('group:open', props.item.id)
    }
    else {
        props.item.data.closed = true
        emits('group:close', props.item.id)
    }
}

function closeChildren() {
    props.item.data.groups.forEach((g: Group) => g.closed = true)
    emits('group:close', props.item.data.groups.map((g: Group) => g.id))
}

</script>

<template>
    <div class="d-flex flex-row group-line m-0 p-0 overflow-hidden" @mouseenter="hoverGroup = true"
        @mouseleave="hoverGroup = false">
        <div v-for="parentId in props.parentIds" style="cursor: pointer;" class="ps-2" @click="$emit('scroll', parentId)"
            @mouseenter="$emit('hover', parentId)" @mouseleave="$emit('unhover')">
            <div class="group-line-border" :class="props.hoverBorder == parentId ? 'active' : ''"></div>
        </div>
        <div @click="toggleClosed" class="align-self-center me-2" style="cursor: pointer;">
            <i v-if="closed" class="bi bi-caret-right-fill" style="margin-left: 1px;"></i>
            <i v-else class="bi bi-caret-down-fill" style="margin-left: 1px;"></i>
        </div>
        <div class="me-1"><SelectCircle :small="true"/></div>
        <div v-if="property != undefined" :style="'font-size: ' + (Math.max(17 - (1 * props.item.depth), 10)) + 'px;'" class="align-self-center me-2">
            <PropertyValue :value="props.item.data.propertyValues[props.item.data.propertyValues.length-1]" />
        </div>
        <div v-else class="align-self-center me-2"><b>{{ groupName }}</b></div>
        <div class="align-self-center me-2 text-secondary" style="font-size: 11px;">{{ group.count }} Images</div>
        <div v-if="group.groups" class="align-self-center me-2 text-secondary" style="font-size: 11px;">{{
            group.groups.length }} Groupes</div>

        <div class="d-flex flex-row align-self-center me-2" v-if="!closed && !props.hideOptions">
            <div v-if="(hasImages || hasPiles) && !hasSubgroups" class="ms-2">
                <StampDropdown :images="images" />
            </div>
            <div class="ms-2" v-if="!hasSubgroups">
                <div class="button" @click="computeClusters">Créer clusters</div>
                <!-- <div class="button">Créer clusters</div> -->
            </div>
            <div v-if="(hasImages || hasPiles) && !hasSubgroups" style="margin-left: 2px;">
                <input class="no-spin" type="number" v-model="props.item.nbClusters" style="width: 30px;" />
            </div>
            <div v-if="(hasImages || hasPiles) && !hasSubgroups && !group.isCluster && someValue" class="ms-2">
                <div class="button" @click="recommandImages">Images Similaires</div>
            </div>
            <div v-if="(hasImages || hasPiles) && hasSubgroups" class="ms-2">
                <div class="button" @click="clear">Clear</div>
            </div>
        </div>

        <div v-if="hasSubgroups && hoverGroup && hasOpenChildren" class="ms-1 text-secondary align-self-center close-children"
            @click="closeChildren">
            Reduire
        </div>

    </div>
</template>

<style scoped>
.close-children {
    font-size: 11px;
    cursor: pointer;
}

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