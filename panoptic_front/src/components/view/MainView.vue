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
import { useProjectStore } from '@/data/projectStore';
import { getSimilarImagesFromText } from '@/utils/utils';

const store = useProjectStore()
const tabManager = store.getTabManager()

const props = defineProps({
    tabId: Number,
    height: Number
})

let firstCompute = false
const recoGroup = ref({} as Group)

const filterElem = ref(null)
const boxElem = ref(null)
const imageList = ref(null)

// images searched by test
const searchedImages = ref([])

const scrollerHeight = ref(0)
const scrollerWidth = ref(0)

const computeStatus = reactive({ groups: false })

const sha1Mode = computed(() => tabManager.getSha1Mode())
const visibleProperties = computed(() => tabManager.getVisibleProperties())

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

tabManager.collection.groupManager.onChange.addListener(() => {
    if (imageList.value) {
        imageList.value.computeLines()
    }
})

function setRecoImages(groupId: string) {
    console.log('set reco', groupId)
    recoGroup.value = tabManager.collection.groupManager.result.index[groupId]
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
    tabManager.load(store.data.tabs[props.tabId])
}

onMounted(async () => {
    loadTab()
})

onMounted(() => {
    scrollerWidth.value = filterElem.value.clientWidth
    window.addEventListener('resize', () => {
        nextTick(() => {
            scrollerWidth.value = filterElem.value?.clientWidth ?? scrollerWidth.value
        })
    })
})

watch(tabManager.state, () => {
    store.updateTab(tabManager.state)
}, { deep: true })
watch(() => tabManager.state.imageSize, () => nextTick(updateScrollerHeight))
watch(() => props.height, async () => {
    await nextTick(updateScrollerHeight)
    // console.log('watch', props.height)
    if(!firstCompute) {
        tabManager.collection.update(store.imageList)
        firstCompute = true
    }
})

watch(() => props.tabId, loadTab)

</script>

<template>
    <div class="" ref="filterElem">
        <ContentFilter :tab="tabManager" :compute-status="computeStatus" @search-images="setSearchedImages" />
    </div>
    <div ref="boxElem" class="m-0 p-0">
        <div v-if="recoGroup.id" class="m-0 p-0">
            <RecommendedMenu :group="recoGroup" :image-size="tabManager.state.imageSize" :width="scrollerWidth" :height="50"
                @close="closeReco" @scroll="imageList.scrollTo" @update="nextTick(() => updateScrollerHeight())" />
        </div>
    </div>
    <div v-if="scrollerWidth > 0 && scrollerHeight > 0" style="margin-left: 10px;">
        <!-- <button @click="imageList.computeLines()">test</button> -->
        <template v-if="tabManager.state.display == 'tree'">
            <TreeScroller :group-manager="tabManager.collection.groupManager" :image-size="tabManager.state.imageSize"
                :height="scrollerHeight - 0" :properties="visibleProperties"
                :selected-images="tabManager.collection.groupManager.selectedImages" ref="imageList"
                :width="scrollerWidth - 10" @recommend="setRecoImages" />
        </template>
        <template v-if="tabManager.state.display == 'grid'">
            <div :style="{ width: (scrollerWidth - 12) + 'px' }" class="p-0 m-0 grid-container">
                <GridScroller :manager="tabManager.collection.groupManager" :height="scrollerHeight - 15"
                    :width="scrollerWidth - 40" :selected-properties="visibleProperties" class="p-0 m-0" :show-images="true"
                    :selected-images="tabManager.collection.groupManager.selectedImages" ref="imageList" />
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