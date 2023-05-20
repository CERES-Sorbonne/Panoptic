<script setup lang="ts">
import { reactive, computed, watch, onMounted, ref } from 'vue';
import ImageGroup from './ImageGroup.vue';
import { globalStore } from '../../data/store';
import { computeGroupFilter } from '@/utils/filter';
import { Group, Image, PropertyType, Tab } from '@/data/models';
import { DefaultDict } from '@/utils/helpers'
import PaginatedImages from './PaginatedImages.vue';
import ContentFilter from './ContentFilter.vue';

const props = defineProps({
    tab: Object as () => Tab
})

const filters = computed(() => props.tab.data.filter)
const groups = computed(() => props.tab.data.groups)
const sorts = computed(() => props.tab.data.sortList)

const imageGroups = reactive([])

const filteredImages = computed(() => {
    let images = Object.values(globalStore.images)
    return images.filter(img => computeGroupFilter(img, filters.value))
})

let nbClusters = ref(10)

function computeGroups() {
    imageGroups.length = 0
    let rootGroup = {
        name: '__all__',
        images: filteredImages.value,
        groups: [],
        count: filteredImages.value.length,
        propertyId: undefined
    } as Group
    if (groups.value.length > 0) {
        rootGroup = computeSubgroups(rootGroup, groups.value)
        imageGroups.push(...rootGroup.groups)
    }
    else {
        imageGroups.push(rootGroup)
    }
}

async function computeMLGroups(groupId: number = null){
    let sha1List: [[string]]
    if(groupId){
        let images = []
        if(imageGroups[groupId].images.length === 0){
            images = imageGroups[groupId].groups.map((group:Group) => group.images).flat().map((i: Image) => i.sha1)
        }
        else{
            images = imageGroups[groupId].images.map((i: Image) => i.sha1)
        }
        imageGroups[groupId].groups = []
        imageGroups[groupId].images = []
        sha1List = await globalStore.getMLGroups(Math.min(nbClusters.value, images.length), images)
    }
    else{
        imageGroups.length = 0
        sha1List = await globalStore.getMLGroups(nbClusters.value)
    }
    const ml_groups = sha1List.map(group => group.map(sha1 => globalStore.images[sha1]))

    for(let [index, group] of ml_groups.entries()){
        let realGroup: Group = {
            name: 'cluster ' + index.toString(),
            images: group,
            count:group.length,
            groups: []
        }
        if(groupId){
            imageGroups[groupId].groups.push(realGroup)
        }
        else{
            imageGroups.push(realGroup)
        }
    }
}

function computeSubgroups(parentGroup: Group, groupList: number[]) {
    let images = parentGroup.images
    let propertyId = groupList[0]
    let groups = new DefaultDict(Array) as { [k: string | number]: any }
    let type = globalStore.properties[propertyId].type

    for (let img of images) {
        let value = propertyId in img.properties ? img.properties[propertyId].value : "undefined"
        if (value == null || value == '') {
            value = undefined
        }
        if (type == PropertyType.checkbox && value != true) {
            value = false
        }
        if (Array.isArray(value)) {
            value.forEach((v: any) => groups[v].push(img))
        }
        else {
            groups[value].push(img)
        }
    }
    let res = []
    for (let group in groups) {
        res.push({
            name: group,
            images: groups[group],
            groups: undefined,
            count: groups[group].length,
            propertyId: propertyId
        })
    }

    if (groupList.length > 1) {
        res.map(g => computeSubgroups(g, groupList.slice(1)))
    }

    parentGroup.groups = res
    parentGroup.images = []
    return parentGroup
}

onMounted(computeGroups)


watch(props, () => {
    globalStore.updateTab(props.tab)
}, { deep: true })

watch(filteredImages, computeGroups, { deep: true })
watch(groups, computeGroups, { deep: true })

</script>

<template>
    <div class="m-2">
        <ContentFilter :tab="props.tab" @compute-ml="computeMLGroups"/>
    </div>
    <hr class="custom-hr"/>
    <div class="ms-2 mt-2">
        <div v-if="imageGroups.length && imageGroups[0].name == '__all__'">
            <PaginatedImages :images="imageGroups[0].images" :imageSize="props.tab.data.imageSize" :groupId="'0'"/>
        </div>
        <div v-else>
            <div v-for="(group, index) in imageGroups">
                <button class="me-2" @click="computeMLGroups(index)">Compute Groups</button>
                <input class="text-input d-inline-block" type="number" style="width: 70px;" v-model="nbClusters"/>
                <ImageGroup :leftAlign="true" :group="group" :imageSize="props.tab.data.imageSize" :group-id="String(index)" />
            </div>
        </div>
    </div>
</template>