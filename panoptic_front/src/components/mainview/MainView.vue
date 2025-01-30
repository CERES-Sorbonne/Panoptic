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
import { useProjectStore } from '@/data/projectStore';
import GraphView from '../graphview/GraphView.vue';
import { useDataStore } from '@/data/dataStore';
import DataLoad from '../loading/DataLoad.vue';
import { TabManager } from '@/core/TabManager';
const project = useProjectStore()


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
        scrollerHeight.value = props.height - filterElem.value.clientHeight - boxElem.value.clientHeight - 5
    }
    else if (filterElem.value) {
        scrollerHeight.value = props.height - filterElem.value.clientHeight - 5
    }
    else {
        scrollerHeight.value = 0
    }
}

props.tab.collection.groupManager.onResultChange.addListener(() => {
    if (imageList.value && props.tab.state.display == 'tree') {
        imageList.value.computeLines()
    }
})

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
    scrollerWidth.value = filterElem.value.clientWidth
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
onMounted(() => props.tab.update())

</script>

<template>
    <div id="main-content" ref="filterElem">
        <template v-if="props.filterOpen">
            <ContentFilter :tab="props.tab" :compute-status="computeStatus" />
        </template>
    </div>
    <div ref="boxElem" class="m-0 p-0">
        <div v-if="recoGroup.id" class="m-0 p-0">
            <RecommendedMenu :group="recoGroup" :image-size="props.tab.state.imageSize" :width="scrollerWidth"
                :height="50" @close="closeReco" @scroll="imageList.scrollTo"
                @update="nextTick(() => updateScrollerHeight())" />
        </div>
    </div>
    <div v-if="data.isLoaded && scrollerWidth > 0 && scrollerHeight > 0 && valid" style="margin-left: 10px;">
        <!-- <button @click="imageList.computeLines()">test</button> -->
        <template v-if="props.tab.state.display == 'tree'">
            <TreeScroller :group-manager="props.tab.collection.groupManager" :image-size="props.tab.state.imageSize"
                :height="scrollerHeight - 0" :properties="visibleProperties" :hide-if-modal="true"
                :selected-images="props.tab.collection.groupManager.selectedImages" ref="imageList"
                :width="scrollerWidth - 25" @recommend="setRecoImages" />
        </template>
        <template v-if="props.tab.state.display == 'grid'">
            <div :style="{ width: (scrollerWidth - 12) + 'px' }" class="p-0 m-0 grid-container">
                <GridScroller :manager="props.tab.collection.groupManager" :height="scrollerHeight - 15"
                    :width="scrollerWidth - 40" :selected-properties="visibleProperties" class="p-0 m-0"
                    :show-images="true" :selected-images="props.tab.collection.groupManager.selectedImages"
                    ref="imageList" :hide-if-modal="true" />
            </div>
        </template>
        <template v-if="props.tab.state.display == 'graph'">
            <GraphView :collection="props.tab.collection" :height="scrollerHeight - 15" />
        </template>

    </div>
</template>

<style scoped>
.grid-container {
    overflow-y: hidden;
    overflow-x: overlay;
}
</style>