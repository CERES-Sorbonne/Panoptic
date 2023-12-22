<script setup lang="ts">

/** MainView
 *  MainView of the open Tab
 */

import { reactive, computed, watch, onMounted, ref, nextTick } from 'vue';
import ContentFilter from './ContentFilter.vue';

import GridScroller from '../scrollers/grid/GridScroller.vue';
import RecommendedMenu from '../images/RecommendedMenu.vue';
import TreeScroller from '../scrollers/tree/TreeScroller.vue';
import { Group } from '@/core/GroupManager';
import { TabManager } from '@/core/TabManager';
import { useStore } from '@/data/store2';
import { getSimilarImagesFromText } from '@/utils/utils';

const store = useStore()

const props = defineProps({
    tabId: Number,
    height: Number
})

const tab = new TabManager()

const recoGroup = ref({} as Group)

const filterElem = ref(null)
const boxElem = ref(null)
const imageList = ref(null)

// images searched by test
const searchedImages = ref([])

const scrollerHeight = ref(0)
const scrollerWidth = ref(0)

const computeStatus = reactive({ groups: false })

const sha1Mode = computed(() => tab.getSha1Mode())
const visibleProperties = computed(() => tab.getVisibleProperties())

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

tab.collection.groupManager.onChange.addListener(() => {
    if (imageList.value) {
        imageList.value.computeLines()
    }
})

function setRecoImages(groupId: string) {
    console.log('set reco', groupId)
    recoGroup.value = tab.collection.groupManager.result.index[groupId]
    nextTick(() => updateScrollerHeight())
}

async function setSearchedImages(textInput: string) {
    if (textInput === "") {
        searchedImages.value = []
    }
    else {
        searchedImages.value = await getSimilarImagesFromText(textInput)
    }
}

function closeReco() {
    recoGroup.value = {} as Group
    nextTick(() => updateScrollerHeight())
}

function loadTab() {
    tab.load(store.data.tabs[props.tabId])
}

onMounted(() => {
    loadTab()
    tab.collection.updateImages(store.imageList)
    nextTick(updateScrollerHeight)
})

onMounted(() => {
    scrollerWidth.value = filterElem.value.clientWidth
    window.addEventListener('resize', () => {
        nextTick(() => {
            scrollerWidth.value = filterElem.value.clientWidth
        })
    })
})

watch(tab.state, () => {
    store.updateTab(tab.state)
}, { deep: true })
watch(() => tab.state.imageSize, () => nextTick(updateScrollerHeight))

watch(() => props.tabId, loadTab)

</script>

<template>
    <div class="" ref="filterElem">
        <ContentFilter :tab="tab" :compute-status="computeStatus" @search-images="setSearchedImages" />
    </div>
    <div ref="boxElem" class="m-0 p-0">
        <div v-if="recoGroup.id" class="m-0 p-0">
            <RecommendedMenu :group="recoGroup" :image-size="tab.state.imageSize" :width="scrollerWidth" :height="50"
                @close="closeReco" @scroll="imageList.scrollTo" @update="nextTick(() => updateScrollerHeight())" />
        </div>
    </div>
    <div v-if="scrollerWidth > 0 && scrollerHeight > 0" style="margin-left: 10px;">
        <!-- <button @click="imageList.computeLines()">test</button> -->
        <template v-if="tab.state.display == 'tree'">
            <TreeScroller :group-manager="tab.collection.groupManager" :image-size="tab.state.imageSize"
                :height="scrollerHeight - 0" :properties="visibleProperties" :selected-images="tab.collection.groupManager.selectedImages"
                ref="imageList" :width="scrollerWidth - 10" @recommend="setRecoImages" />
        </template>
        <template v-if="tab.state.display == 'grid'">
            <div :style="{ width: (scrollerWidth - 12) + 'px' }" class="p-0 m-0 grid-container">
                <GridScroller :manager="tab.collection.groupManager" :height="scrollerHeight - 15" :width="scrollerWidth - 40"
                    :selected-properties="visibleProperties" class="p-0 m-0" :show-images="true"
                    :selected-images="tab.collection.groupManager.selectedImages" ref="imageList" />
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