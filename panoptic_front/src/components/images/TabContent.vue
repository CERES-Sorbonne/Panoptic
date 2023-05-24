<script setup lang="ts">
import { reactive, computed, watch, onMounted, ref } from 'vue';
import ImageGroup from './ImageGroup.vue';
import { globalStore } from '../../data/store';
import { computeGroupFilter } from '@/utils/filter';
import { Group, Image, PropertyType, Tab } from '@/data/models';
import { DefaultDict } from '@/utils/helpers'
import PaginatedImages from './PaginatedImages.vue';
import ContentFilter from './ContentFilter.vue';
import { sortImages } from '@/utils/sort';

const props = defineProps({
    tab: Object as () => Tab
})

const filters = computed(() => props.tab.data.filter)
const groups = computed(() => props.tab.data.groups)
const sorts = computed(() => props.tab.data.sortList)

const imageGroups = reactive([])

const filteredImages = computed(() => {
    let images = Object.values(globalStore.images)

    if(sorts.value.length > 0) {
        console.log('soort')
        images = sortImages(images, globalStore.properties[sorts.value[0].property_id])
        if(!sorts.value[0].ascending) {
            images.reverse()
        }
    }

    return images.filter(img => computeGroupFilter(img, filters.value))
})
function computeGroups() {
    imageGroups.length = 0
    let rootGroup = {
        name: 'All',
        images: filteredImages.value,
        groups: undefined,
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
        <ContentFilter :tab="props.tab" @compute-ml=""/>
    </div>
    <hr class="custom-hr"/>
    <div class="ms-2 mt-2">
        <div v-if="imageGroups.length && imageGroups[0].name == '__all__'">
            <PaginatedImages :images="imageGroups[0].images" :imageSize="props.tab.data.imageSize" :groupId="'0'"/>
        </div>
        <div v-else>
            <div v-for="(group, index) in imageGroups">
                <ImageGroup :leftAlign="true" :group="group" :imageSize="props.tab.data.imageSize" :group-id="String(index)" />
            </div>
        </div>
    </div>
</template>