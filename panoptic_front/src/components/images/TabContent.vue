<script setup lang="ts">
import { reactive, computed, watch, onMounted, ref, nextTick } from 'vue';
import { globalStore } from '../../data/store';
import { computeGroupFilter } from '@/utils/filter';
import { Group, Tab, GroupData, PropertyValue, SortIndex, Sha1Pile } from '@/data/models';
import ContentFilter from './ContentFilter.vue';
import { sortGroupTree, sortImages } from '@/utils/sort';
import TreeScroller from '@/components/scrollers/tree/TreeScroller.vue'

import RecommendedMenu from './RecommendedMenu.vue';
import { generateGroups, mergeGroup } from '@/utils/groups';
import GridScroller from '../scrollers/grid/GridScroller.vue';

const props = defineProps({
    tab: Object as () => Tab,
    height: Number
})

const reco = reactive({ images: [] as string[], values: [] as PropertyValue[], groupId: undefined })

const filterElem = ref(null)
const boxElem = ref(null)
const imageList = ref(null)

// images searched by test
const searchedImages = ref([])

const scrollerHeight = ref(0)
const scrollerWidth = ref(0)

const computeStatus = reactive({ groups: false })

const filters = computed(() => props.tab.data.filter)
const groups = computed(() => props.tab.data.groups)
const sorts = computed(() => props.tab.data.sortList)

const visibleProperties = computed(() => Object.entries(globalStore.tabs[globalStore.selectedTab].data.visibleProperties).filter(([k, v]) => v).map(([k, v]) => Number(k)).map(k => globalStore.properties[k]))

function updateScrollerHeight() {
    // console.log('update height')
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

const filteredImages = computed(() => {

    let images = Object.values(globalStore.images)

    if (searchedImages.value.length > 0) {
        const sha1ToImage: any = {}
        images.forEach(image => sha1ToImage[image.sha1] = image)
        return searchedImages.value.filter(el => el.dist > 0.25).map(el => sha1ToImage[el.sha1])
    }

    if (Object.keys(props.tab.data.selectedFolders).length > 0) {
        let folderIds = Object.keys(props.tab.data.selectedFolders).map(Number)
        let allIds = [...folderIds] as Array<number>
        folderIds.forEach(id => allIds.push(...globalStore.getFolderChildren(id)))
        if (allIds.length > 0) {
            images = images.filter(img => allIds.includes(img.folder_id))
        }
    }
    // on filtre les images normalement, et aussi en prenant en cmpte que si il y a des images cherchées, ça les renvoie
    let filtered = images.filter(img => computeGroupFilter(img, filters.value))
    return filtered
})

function computeGroups(force = false) {
    if (computeStatus.groups) {
        return
    }
    computeStatus.groups = true

    // compute happens here. Timeout instead of requestIdleCallback for Safari support
    // allows the ui to draw the spinner before cpu blocking
    setTimeout(() => {
        console.time('compute groups')
        let index = generateGroups(filteredImages.value, groups.value)
        let rootGroup = index['0']

        if (!force) {
            for (let id in index) {
                index[id] = mergeGroup(index[id], groupData.index)
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

        sortGroups()

        console.timeEnd('compute groups')

        if (imageList.value)
            nextTick(imageList.value.computeLines)

        computeStatus.groups = false
    }, 10)
}

function sortGroups() {
    const sortIndex: SortIndex = {}
    sorts.value.forEach(s => sortIndex[s.property_id] = s)

    sortGroupTree(groupData.root, groupData.order, sortIndex)

    Object.keys(groupData.index).forEach(key => {
        const group = groupData.index[key]
        if (Array.isArray(group.images) && group.images.length > 0) {
            sortImages(group.images, sorts.value.slice(groups.value.length))
            if (props.tab.data.sha1Mode) {
                imagesToSha1Piles(group)
            }
        }
    })
}

function imagesToSha1Piles(group: Group) {
    const res: Array<Sha1Pile> = []
    const order: { [key: string]: number } = {}

    for (let img of group.images) {
        if (order[img.sha1] === undefined) {
            order[img.sha1] = res.length
            res.push({ sha1: img.sha1, images: [] })
        }
        res[order[img.sha1]].images.push(img)
    }

    group.imagePiles = res
    // group.images = []
}

function setRecoImages(images: string[], propertyValues: PropertyValue[], groupId: string) {
    reco.images.length = 0
    reco.images.push(...images)
    reco.values.length = 0
    reco.values.push(...propertyValues)
    reco.groupId = groupId
    nextTick(() => updateScrollerHeight())
}

async function setSearchedImages(textInput: string) {
    if (textInput === "") {
        searchedImages.value = []
    }
    else {
        searchedImages.value = await globalStore.getSimilarImagesFromText(textInput)
    }
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
watch(sorts, () => {
    sortGroups()
    imageList.value.computeLines()
}, { deep: true })
watch(() => props.tab.data.imageSize, () => nextTick(updateScrollerHeight))
watch(() => props.tab.data.sha1Mode, computeGroups)



</script>

<template>
    <div class="" ref="filterElem">
        <ContentFilter :tab="props.tab" @compute-ml="" :compute-status="computeStatus" @search-images="setSearchedImages"/>
    </div>
    <div ref="boxElem" class="m-0 p-0">
        <div v-if="reco.images.length > 0" class="m-0 p-0">
            <RecommendedMenu :reco="reco" :image-size="tab.data.imageSize" :width="scrollerWidth" :height="50"
                @close="closeReco" @scroll="imageList.scrollTo" />
        </div>
    </div>
    <div v-if="scrollerWidth > 0 && scrollerHeight > 0" style="margin-left: 10px;">
        <template v-if="tab.data.display == 'tree'">
            <TreeScroller :data="groupData" :image-size="props.tab.data.imageSize" :height="scrollerHeight - 0"
                ref="imageList" :width="scrollerWidth - 10" @recommend="setRecoImages" />
        </template>
        <template v-if="tab.data.display == 'grid'">
            <div :style="{ width: (scrollerWidth - 0) + 'px' }" class="p-0 m-0 grid-container">
                <GridScroller :data="groupData" :height="scrollerHeight - 15" ref="imageList"
                    :selected-properties="visibleProperties" class="p-0 m-0" :show-images="true"/>
            </div>
        </template>

    </div>
</template>

<style scoped>
.grid-container {
    overflow-y: hidden;
    overflow-x: overlay;
}
</style>