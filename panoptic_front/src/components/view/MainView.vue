<script setup lang="ts">

/** MainView
 *  MainView of the open Tab
 */

import { reactive, computed, watch, onMounted, ref, nextTick } from 'vue';
import ContentFilter from './ContentFilter.vue';

import GridScroller from '../scrollers/grid/GridScroller.vue';
import { Tab } from '@/data/models';
import { ImageSelector } from '@/utils/selection';
import { globalStore } from '@/data/store';
import RecommendedMenu from '../images/RecommendedMenu.vue';
import TreeScroller from '../scrollers/tree/TreeScroller.vue';
import { Group } from '@/core/GroupManager';

const props = defineProps({
    tab: Object as () => Tab,
    height: Number
})

const groupData = reactive({
    root: undefined,
    index: {},
    order: []
})

const recoGroup = ref({} as Group)

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

// TODO put back for export
const filteredImages = computed(() => [])

props.tab.collection.groupManager.onChange.addListener(() => {
    if (imageList.value) {
        imageList.value.computeLines()
    }
})

// on expose les filteredImages pour pouvoir les utiliser dans la modal d'export des données pour n'exporter que les images affichées dans le tab
defineExpose({ filteredImages })

function setRecoImages(groupId: string) {
    console.log('set reco', groupId)
    recoGroup.value = props.tab.collection.groupManager.result.index[groupId]
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
    recoGroup.value = {} as Group
    nextTick(() => updateScrollerHeight())
}

onMounted(() => props.tab.collection.updateImages(Object.values(globalStore.images)))
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
watch(() => props.tab.data.imageSize, () => nextTick(updateScrollerHeight))

</script>

<template>
    <div class="" ref="filterElem">
        <ContentFilter :tab="props.tab" :compute-status="computeStatus" @search-images="setSearchedImages"
            :selector="selector" />
    </div>
    <div ref="boxElem" class="m-0 p-0">
        <div v-if="recoGroup.id" class="m-0 p-0">
            <RecommendedMenu :group="recoGroup" :image-size="tab.data.imageSize" :width="scrollerWidth" :height="50"
                @close="closeReco" @scroll="imageList.scrollTo" @update="nextTick(() => updateScrollerHeight())" />
        </div>
    </div>
    <div v-if="scrollerWidth > 0 && scrollerHeight > 0" style="margin-left: 10px;">
        <!-- <button @click="imageList.computeLines()">test</button> -->
        <template v-if="tab.data.display == 'tree'">
            <TreeScroller :group-manager="props.tab.collection.groupManager" :image-size="props.tab.data.imageSize"
                :height="scrollerHeight - 0" :properties="visibleProperties" :selected-images="selectedImages"
                ref="imageList" :width="scrollerWidth - 10" @recommend="setRecoImages" :selector="selector" />
        </template>
        <template v-if="tab.data.display == 'grid'">
            <div :style="{ width: (scrollerWidth - 12) + 'px' }" class="p-0 m-0 grid-container">
                <GridScroller :data="groupData" :height="scrollerHeight - 15" :width="scrollerWidth - 40"
                    :selected-properties="visibleProperties" class="p-0 m-0" :show-images="true"
                    :selected-images="selectedImages" :selector="selector" ref="imageList" />
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