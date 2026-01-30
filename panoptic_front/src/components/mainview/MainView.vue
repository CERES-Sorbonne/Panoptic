<script setup lang="ts">

/** MainView
 *  MainView of the open Tab
 */

import { reactive, computed, watch, onMounted, ref, nextTick, onUnmounted } from 'vue';
import ContentFilter from './ContentFilter.vue';

import GridScroller from '../scrollers/grid/GridScroller.vue';
import RecommendedMenu from '../images/RecommendedMenu.vue';
import TreeScroller from '../scrollers/tree/TreeScroller.vue';
import { Group } from '@/core/GroupManager';
import GraphView from '../graphview/GraphView.vue';
import { useDataStore } from '@/data/dataStore';
import { TabManager } from '@/core/TabManager';
import '@/data/socketStore'
import MapView from '../mapview/MapView.vue';
import { useTabStore } from '@/data/tabStore';

const tabs = useTabStore()

const data = useDataStore()

const props = defineProps<{
    tab: TabManager
    height: number
    filterOpen: boolean
}>()

defineExpose({
    updateScrollerWidth
})

const recoGroup = ref({} as Group)

const valid = ref(true)
const filterElem = ref(null)
const boxElem = ref(null)
const imageList = ref(null)

// images searched by test

const scrollerHeight = ref(0)
const scrollerWidth = ref(0)

const computeStatus = reactive({ groups: false })

const visibleProperties = computed(() => props.tab.getVisibleProperties())

function updateScrollerHeight() {
    if (filterElem.value && boxElem.value) {
        scrollerHeight.value = props.height - filterElem.value.clientHeight - boxElem.value.clientHeight
    }
    else if (filterElem.value) {
        scrollerHeight.value = props.height - filterElem.value.clientHeight
    }
    else {
        scrollerHeight.value = 0
    }
}

function setRecoImages(groupId: number) {
    recoGroup.value = props.tab.collection.groupManager.result.index[groupId]
    nextTick(() => updateScrollerHeight())
}

function closeReco() {
    recoGroup.value = {} as Group
    nextTick(() => updateScrollerHeight())
}

async function updateScrollerWidth() {
    await nextTick()
    scrollerWidth.value = filterElem.value?.clientWidth ?? scrollerWidth.value
}

onMounted(() => {
    updateScrollerWidth()
    window.addEventListener('resize', updateScrollerWidth)
})

onUnmounted(() => {
    window.removeEventListener('resize', updateScrollerWidth)
})

watch(() => props.tab.state.imageSize, () => nextTick(updateScrollerHeight))
watch(() => props.filterOpen, () => nextTick(updateScrollerHeight))
watch(() => props.height, async () => {
    await nextTick(updateScrollerHeight)
})

onMounted(updateScrollerHeight)

</script>

<template>
    <div id="main-content" ref="filterElem">
        <template v-if="props.filterOpen">
            <ContentFilter :tab="props.tab" :compute-status="computeStatus" />
        </template>
    </div>
    <div ref="boxElem" class="m-0 p-0">
        <div v-if="recoGroup.id" class="m-0 p-0">
            <RecommendedMenu :tab="props.tab" :group="recoGroup" :image-size="props.tab.state.imageSize" :width="scrollerWidth"
                :height="50" @close="closeReco" @scroll="imageList.scrollTo"
                @update="nextTick(() => updateScrollerHeight())" />
        </div>
    </div>
    <div v-if="data.isLoaded && scrollerWidth > 0 && scrollerHeight > 0 && valid">
        <!-- <button @click="imageList.computeLines()">test</button> -->
        <template v-if="props.tab.state.display == 'tree'" >
            <TreeScroller input-key="main-view-tree" :group-manager="props.tab.collection.groupManager" :image-size="props.tab.state.imageSize"
                :height="scrollerHeight" :properties="visibleProperties" :hide-if-modal="true"
                :selected-images="props.tab.collection.groupManager.selectedImages" ref="imageList"
                :width="scrollerWidth -20" @recommend="setRecoImages"  style="margin-left: 10px;"/>
        </template>
        <template v-if="props.tab.state.display == 'grid'">
            <div :style="{ width: (scrollerWidth - 12) + 'px' }" class="grid-container" style="margin-left: 10px;">
                <GridScroller :tab="tab" :manager="props.tab.collection.groupManager" :height="scrollerHeight - 15"
                    :width="scrollerWidth -12" :selected-properties="visibleProperties" class="p-0 m-0"
                    :show-images="true" :selected-images="props.tab.collection.groupManager.selectedImages"
                    ref="imageList" :hide-if-modal="true"  />
            </div>
        </template>
        <template v-if="props.tab.state.display == 'graph'">
            <GraphView :collection="props.tab.collection" :height="scrollerHeight - 15"  style="margin-left: 10px;"/>
        </template>
        <template v-if="props.tab.state.display == 'map' && tabs.loaded">
           <MapView :style="{height: scrollerHeight - 0 + 'px'}" :tab="props.tab" /> 
        </template>

    </div>
</template>

<style scoped>
.grid-container {
    overflow-y: hidden;
    overflow-x: overlay;
}
</style>