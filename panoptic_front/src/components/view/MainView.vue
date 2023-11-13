<script setup lang="ts">
import { reactive, computed, watch, onMounted, ref, nextTick } from 'vue';
import ContentFilter from './ContentFilter.vue';

import GridScroller from '../scrollers/grid/GridScroller.vue';
import { GroupData, PropertyValue, SortIndex, Tab } from '@/data/models';
import { ImageSelector } from '@/utils/selection';
import { globalStore } from '@/data/store';
import { FilterManager, computeGroupFilter } from '@/utils/filter';
import { generateGroupData, imagesToSha1Piles, mergeGroup } from '@/utils/groups';
import { sortGroupData, sortGroupTree, sortImages } from '@/utils/sort';
import RecommendedMenu from '../images/RecommendedMenu.vue';
import TreeScroller from '../scrollers/tree/TreeScroller.vue';

const props = defineProps({
    tab: Object as () => Tab,
    height: Number
})

const groupData = reactive({
    root: undefined,
    index: {},
    order: []
}) as GroupData

const reco = reactive({ images: [] as string[], values: [] as PropertyValue[], groupId: undefined })

const selectedImages = reactive({}) as { [imgId: string]: boolean }

const selectedImages2 = reactive(new Set<number>())
const selector = new ImageSelector(groupData, selectedImages2)

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

const sha1Mode = computed(() => globalStore.getTab().data.sha1Mode)
const visibleProperties = computed(() => globalStore.getVisibleViewProperties())



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

// on expose les filteredImages pour pouvoir les utiliser dans la modal d'export des données pour n'exporter que les images affichées dans le tab
defineExpose({ filteredImages })

function computeGroups(force = false) {
    if (computeStatus.groups) {
        return
    }
    computeStatus.groups = true

    // compute happens here. Timeout instead of requestIdleCallback for Safari support
    // allows the ui to draw the spinner before cpu blocking
    setTimeout(() => {
        console.time('compute groups')
        // let index = generateGroups(filteredImages.value, groups.value)
        // let rootGroup = index['0']

        let data = generateGroupData(filteredImages.value, groups.value, sha1Mode.value)
        let index = data.index
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

        // groupData.index = index
        // groupData.root = rootGroup
        // groupData.order = []

        // sortGroups()
        sortGroupData(data, sorts.value, sha1Mode.value)

        Object.assign(groupData, data)

        console.timeEnd('compute groups')

        if (imageList.value)
            nextTick(imageList.value.computeLines)

        computeStatus.groups = false
    }, 10)
}

function sortGroups() {
    if (!groupData.root) return
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
    if (imageList.value) imageList.value.computeLines()
}, { deep: true })
watch(() => props.tab.data.imageSize, () => nextTick(updateScrollerHeight))
watch(() => props.tab.data.sha1Mode, computeGroups)



</script>

<template>
    <div class="" ref="filterElem">
        <ContentFilter :tab="props.tab" @compute-ml="" :compute-status="computeStatus" @search-images="setSearchedImages"
            :selector="selector" :filter-manager="props.tab.data.filterManager" />
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
                :properties="visibleProperties" :selected-images="selectedImages" ref="imageList"
                :width="scrollerWidth - 10" @recommend="setRecoImages" :selector="selector" />
        </template>
        <template v-if="tab.data.display == 'grid'">
            <div :style="{ width: (scrollerWidth - 12) + 'px' }" class="p-0 m-0 grid-container">
                <GridScroller :data="groupData" :height="scrollerHeight - 15" :width="scrollerWidth - 40"
                    :selected-properties="visibleProperties" class="p-0 m-0" :show-images="true"
                    :selected-images="selectedImages" :selector="selector" ref="imageList"/>
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