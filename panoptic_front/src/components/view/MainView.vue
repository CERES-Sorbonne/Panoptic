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
import GraphView from '../graphview/GraphView.vue';
import { getTabManager } from '@/utils/utils';
const project = useProjectStore()
const tabManager = getTabManager()

const props = defineProps({
    tabId: Number,
    height: Number
})

const recoGroup = ref({} as Group)

const filterElem = ref(null)
const boxElem = ref(null)
const imageList = ref(null)

// images searched by test

const scrollerHeight = ref(0)
const scrollerWidth = ref(0)

const computeStatus = reactive({ groups: false })

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
    if (imageList.value && tabManager.state.display == 'tree') {
        imageList.value.computeLines()
    }
})

function setRecoImages(groupId: string) {
    recoGroup.value = tabManager.collection.groupManager.result.index[groupId]
    nextTick(() => updateScrollerHeight())
}

function closeReco() {
    recoGroup.value = {} as Group
    nextTick(() => updateScrollerHeight())
}

onMounted(() => {
    scrollerWidth.value = filterElem.value.clientWidth
    window.addEventListener('resize', () => {
        nextTick(() => {
            scrollerWidth.value = filterElem.value?.clientWidth ?? scrollerWidth.value
        })
    })
})

watch(() => tabManager.state.imageSize, () => nextTick(updateScrollerHeight))
watch(() => props.height, async () => {
    await nextTick(updateScrollerHeight)
})

</script>

<template>
    <div id="main-content" ref="filterElem">
        <ContentFilter :tab="tabManager" :compute-status="computeStatus" />
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
                :height="scrollerHeight - 0" :properties="visibleProperties" :hide-if-modal="true"
                :selected-images="tabManager.collection.groupManager.selectedImages" ref="imageList"
                :width="scrollerWidth - 25" @recommend="setRecoImages" />
        </template>
        <template v-if="tabManager.state.display == 'grid'">
            <div :style="{ width: (scrollerWidth - 12) + 'px' }" class="p-0 m-0 grid-container">
                <GridScroller :manager="tabManager.collection.groupManager" :height="scrollerHeight - 15"
                    :width="scrollerWidth - 40" :selected-properties="visibleProperties" class="p-0 m-0" :show-images="true"
                    :selected-images="tabManager.collection.groupManager.selectedImages" ref="imageList" :hide-if-modal="true" />
            </div>
        </template>
        <template v-if="tabManager.state.display == 'graph'">
            <GraphView :collection="tabManager.collection" :height="scrollerHeight -15" />
        </template>

    </div>
</template>

<style scoped>
.grid-container {
    overflow-y: hidden;
    overflow-x: overlay;
}
</style>