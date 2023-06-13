<script setup lang="ts">
import { reactive, computed, watch, onMounted, ref, nextTick } from 'vue';
import { globalStore } from '../../data/store';
import { computeGroupFilter } from '@/utils/filter';
import { Group, GroupIndex, PropertyType, Tab, GroupData, Image, PropertyValue } from '@/data/models';
import { DefaultDict } from '@/utils/helpers'
import ContentFilter from './ContentFilter.vue';
import { sortGroupTree, sortImages } from '@/utils/sort';
import ImageList from './ImageList.vue';

import moment from 'moment';
import RecommendedMenu from './RecommendedMenu.vue';
import { UNDEFINED_KEY } from '@/utils/groups';

const props = defineProps({
    tab: Object as () => Tab,
    height: Number
})

const reco = reactive({ images: [] as string[], values: [] as PropertyValue[], groupId: undefined })

const filterElem = ref(null)
const boxElem = ref(null)
const imageList = ref(null)

const scrollerHeight = ref(0)
const scrollerWidth = ref(0)

const computeStatus = reactive({ groups: false })

const filters = computed(() => props.tab.data.filter)
const groups = computed(() => props.tab.data.groups)
const sorts = computed(() => props.tab.data.sortList)

function updateScrollerHeight() {
    if (filterElem.value && boxElem.value) {
        scrollerHeight.value = props.height - filterElem.value.clientHeight - boxElem.value.clientHeight - 5
    }
    else if (filterElem.value) {
        scrollerHeight.value = props.height - filterElem.value.clientHeight - 5
    }
    else {
        scrollerHeight.value = 0
    }
}

const groupData = reactive({
    root: undefined,
    index: {},
    order: []
}) as GroupData

const imageGroups = reactive({}) as Group

const filteredImages = computed(() => {
    let images = Object.values(globalStore.images)

    if (Object.keys(props.tab.data.selectedFolders).length > 0) {
        let folderIds = Object.keys(props.tab.data.selectedFolders).map(Number)
        let allIds = [...folderIds] as Array<number>
        folderIds.forEach(id => allIds.push(...globalStore.getFolderChildren(id)))
        if (allIds.length > 0) {
            images = images.filter(img => allIds.includes(img.folder_id))
        }
    }

    let filtered = images.filter(img => computeGroupFilter(img, filters.value))

    if (sorts.value.length > 0) {
        filtered = sortImages(filtered, globalStore.properties[sorts.value[0].property_id])
        if (!sorts.value[0].ascending) {
            filtered.reverse()
        }
    }

    return filtered
})

function computeGroups(force = false) {
    if (computeStatus.groups) {
        return
    }
    computeStatus.groups = true

    requestIdleCallback(() => {
        console.time('compute groups')
        let index = {} as GroupIndex
        let rootGroup = generateGroups(index)

        if (!force) {
            for (let id in index) {
                index[id] = mergeGroup(index[id])
            }

            for (let id in groupData.index) {
                let group = groupData.index[id]
                if (group.isCluster) {
                    index[group.id] = group
                }
            }
        }

        groupData.index = index
        groupData.root = rootGroup
        groupData.order = []
        sortGroupTree(groupData.root, groupData.order)

        console.timeEnd('compute groups')

        if (imageList.value)
            nextTick(imageList.value.computeLines)

        computeStatus.groups = false
    })
}

function mergeGroup(update: Group) {
    let index = groupData.index
    // console.log('merge: ' + update.id)

    let id = update.id

    if (index[id] == undefined) {
        return update
    }
    // console.log('closed: ' + index[id].closed)

    update.allSimilarSha1s = index[id].allSimilarSha1s
    update.similarSha1sBlacklist = index[id].similarSha1sBlacklist
    update.getSimilarImages = index[id].getSimilarImages

    update.closed = index[id].closed
    let childrenIds = index[id].children
    if (!childrenIds || childrenIds.length == 0) {
        return update
    }

    // let children = childrenIds.map(id => index[id]).filter(c => c != undefined).filter(c => c.propertyId == undefined)
    let children = index[id].groups
    if (Array.isArray(index[id].images) && index[id].images.length > 0 && children && children.length > 0) {
        update.children = children.map(c => c.id)
        update.groups = children
    }
    return update
}

function generateGroups(index: GroupIndex) {
    let rootGroup = {
        name: 'All',
        images: filteredImages.value,
        groups: undefined as Group[],
        count: filteredImages.value.length,
        propertyId: undefined,
        id: '0',
        depth: 0,
        parentId: undefined,
        propertyValues: []
    } as Group
    if (groups.value.length > 0) {
        rootGroup = computeSubgroups(rootGroup, groups.value, index)
    }
    index[rootGroup.id] = rootGroup
    return rootGroup
}



function computeSubgroups(parentGroup: Group, groupList: number[], index: GroupIndex) {
    let images = parentGroup.images
    let propertyId = groupList[0]
    let groups = new DefaultDict(Array) as { [k: string | number]: any }
    let type = globalStore.properties[propertyId].type

    for (let img of images) {
        let value = propertyId in img.properties ? img.properties[propertyId].value : UNDEFINED_KEY
        if (value == null || value == '') {
            value = UNDEFINED_KEY
        }
        else if (type == PropertyType.checkbox && value != true) {
            value = false
        }

        if (Array.isArray(value)) {
            value.forEach((v: any) => groups[v].push(img))
        }
        else if (type == PropertyType.date) {
            groups[moment(value).format('YYYY/MM')].push(img)
        }
        else {
            groups[value].push(img)
        }
    }
    let res = [] as Group[]
    for (let key in groups) {
        let newGroup = {
            name: key,
            images: groups[key],
            groups: undefined as Group[],
            count: groups[key].length,
            propertyId: propertyId,
            id: parentGroup.id + '-' + propertyId + '-' + key,
            depth: parentGroup.depth + 1,
            parentId: parentGroup.id,
            propertyValues: [...parentGroup.propertyValues, { propertyId, value: key }]
        }
        res.push(newGroup)
    }

    if (groupList.length > 1) {
        res.map(g => computeSubgroups(g, groupList.slice(1), index))
    }

    parentGroup.groups = res
    parentGroup.children = res.map(g => g.id)
    parentGroup.images = []
    res.forEach(g => index[g.id] = g)
    return parentGroup
}

function setRecoImages(images: string[], propertyValues: PropertyValue[], groupId: string) {
    reco.images.length = 0
    reco.images.push(...images)
    reco.values.length = 0
    reco.values.push(...propertyValues)
    reco.groupId = groupId
    nextTick(() => updateScrollerHeight())
}

function closeReco() {
    reco.images.length = 0
    reco.values.length = 0
    nextTick(() => updateScrollerHeight())
}

onMounted(computeGroups)
onMounted(() => nextTick(updateScrollerHeight))
onMounted(() => {
    scrollerWidth.value = filterElem.value.clientWidth
    window.addEventListener('resize', () => {
        nextTick(() => {
            scrollerWidth.value = filterElem.value.clientWidth
        })
    })
})

watch(props, () => {
    globalStore.updateTab(props.tab)
}, { deep: true })

watch(filteredImages, () => computeGroups(), { deep: true })
watch(groups, () => {
    computeGroups(true)
    if (groupData.index[reco.groupId] == undefined) {
        closeReco()
    }
}, { deep: true })
watch(sorts, () => computeGroups(), { deep: true })
watch(() => props.tab.data.imageSize, () => nextTick(updateScrollerHeight))



</script>

<template>
    <div class="" ref="filterElem">
        <ContentFilter :tab="props.tab" @compute-ml="" :compute-status="computeStatus" />
    </div>
    <div ref="boxElem" class="m-0 p-0">
        <div v-if="reco.images.length > 0" class="m-0 p-0">
            <RecommendedMenu :reco="reco" :image-size="tab.data.imageSize" :width="scrollerWidth" :height="50"
                @close="closeReco" @scroll="imageList.scrollTo" />
        </div>
    </div>
    <div v-if="scrollerWidth > 0 && scrollerHeight > 0" style="margin-left: 10px;">
        <ImageList :data="groupData" :image-size="props.tab.data.imageSize" :height="scrollerHeight - 20" ref="imageList"
            :width="scrollerWidth - 10" @recommend="setRecoImages" />
    </div>
</template>