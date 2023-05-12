<script setup lang="ts">
import { reactive, computed, watch, onMounted, ref } from 'vue';
import ImageGroup from './ImageGroup.vue';
import { globalStore } from '../../data/store';
import { computeGroupFilter } from '@/utils/filter';
import FilterForm from '../forms/FilterForm.vue';
import GroupForm from '../forms/GroupForm.vue';
import SortForm from '../forms/SortForm.vue';
import { Group, Image, PropertyType } from '@/data/models';
import { DefaultDict } from '@/utils/helpers'
import PaginatedImages from './PaginatedImages.vue';

const props = defineProps({
    tabIndex: Number
})

const imageSize = ref('100')

const tab = computed(() => globalStore.tabs[props.tabIndex])
const filters = computed(() => tab.value.filter)
const groups = computed(() => tab.value.groups)
const sorts = computed(() => tab.value.sortList)

const imageGroups = reactive([])

const filteredImages = computed(() => {
    let images = Object.values(globalStore.images)
    return images.filter(img => computeGroupFilter(img, filters.value))
})

function computeGroups() {
    imageGroups.length = 0
    let rootGroup = {
        name: '__all__',
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
    console.log('compute subgroup for property: ' + groupList[0])
    let images = parentGroup.images
    let propertyId = groupList[0]
    let groups = new DefaultDict(Array) as { [k: string | number]: any }
    let type = globalStore.properties[propertyId].type

    for (let img of images) {
        let value = propertyId in img.properties ? img.properties[propertyId].value : "undefined"
        if (value == null) {
            value == undefined
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


watch(tab, () => {
    globalStore.saveTabState()
}, { deep: true })

watch(filteredImages, computeGroups, { deep: true })
watch(groups, computeGroups, { deep: true })

</script>

<template>
    <!-- {{ imageGroups }} -->
    <!-- <div class="d-flex flex-wrap mb-3 mt-3">
        <div class="bd-highlight mt-1 me-1">
            <div class="input-group">
                <div class="input-group-text">Display</div>
                <DropdownInput :options="options.display" v-model="state.display" />
            </div>
        </div>
        <div class="bd-highlight mt-1 me-1">
            <ListInput label="Filters" :selected="state.filter" :possible="options.filter" />
        </div>
        <div class="bd-highlight mt-1 me-1">
            <ListInput label="GroupBy" :selected="state.groupBy" :possible="options.groupBy" />
        </div>
    </div> -->

    <div class="d-flex flex-wrap mb-3 mt-3">
        <FilterForm :filter="globalStore.tabs[props.tabIndex].filter" />
        <GroupForm :groupIds="globalStore.tabs[props.tabIndex].groups" />
        <SortForm :sortList="globalStore.tabs[props.tabIndex].sortList" />
    </div>


    <div class="mt-4">
        <i class="h2 bi bi-aspect-ratio me-3"></i>
        <input type="range" class="form-range" id="rangeImageSize" min="50" max="200" v-model="imageSize"
            style="width: 300px;">
        <span class="ms-2">({{ imageSize }}px)</span>
        <div class="float-end me-5">
            <div class="input-group">
                <div class="input-group-text">PageSize</div>
                <input class="form-control" type="number" v-model="globalStore.settings.pageSize" style="width: 100px;" />
            </div>
        </div>
        <PaginatedImages v-if="imageGroups.length > 0 && imageGroups[0].name == '__all__'" :images="imageGroups[0].images" :imageSize="imageSize" />
        <template v-else>
            <ImageGroup :leftAlign="true" v-for="group in imageGroups" :group="group" :imageSize="imageSize" />
        </template>
    </div>
</template>