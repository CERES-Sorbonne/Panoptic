<script setup lang="ts">
// A single view island root node — wraps the image visualisation in a growing
// island card. Used once per pane in the center view split.
import { computed, onMounted, onUnmounted, ref } from 'vue'
import IslandPanel from '@/layouts/IslandPanel.vue'
import RangeInput from '@/components/inputs/RangeInput.vue'
import ViewSelectionDropdown from '@/components/layoutpanels/ViewSelectionDropdown.vue'
import TreeScroller from '@/components/scrollers/tree/TreeScroller.vue'
import GridScroller from '@/components/scrollers/grid/GridScroller.vue'
import GraphView from '@/components/graphview/GraphView.vue'
import MapView from '@/components/mapview/MapView.vue'
import wTT from '@/components/tooltips/withToolTip.vue'
import { useTabStore } from '@/data/tabStore'

const tabStore = useTabStore()

const containerRef = ref<HTMLElement>()
const dimensions = ref({ width: 0, height: 0 })
const currentTab = tabStore.getMainTab()
const visibleProperties = computed(() => tabStore.getMainTab()?.getVisibleProperties() ?? [])

function onResize(entries: ResizeObserverEntry[]) {
    for (const entry of entries) {
        const { width, height } = entry.contentRect
        dimensions.value = { width, height }
    }
}

let observer: ResizeObserver | null = null

onMounted(() => {
    if (containerRef.value) {
        observer = new ResizeObserver(onResize)
        observer.observe(containerRef.value)
    }
})

onUnmounted(() => {
    if (observer && containerRef.value) {
        observer.unobserve(containerRef.value)
    }
})

</script>

<template>
    <IslandPanel grow>
        <template #header>
            <div class="view-header-bar">
                <!-- View type selection dropdown -->
                <ViewSelectionDropdown />

                <!-- Image size range -->
                <div class="ms-3 d-flex align-items-center">
                    <wTT message="main.menu.image_size_tooltip" :click="false">
                        <div class="bi bi-aspect-ratio me-1"></div>
                    </wTT>
                    <RangeInput :min="30" :max="500" v-model="currentTab.state.imageSize" />
                </div>

                <div class="flex-grow-1"></div>
            </div>
        </template>

        <div ref="containerRef" class="view-container">
            <TreeScroller
                v-if="currentTab && currentTab.state.display == 'tree' && dimensions.width > 0"
                input-key="view-panel-tree"
                :group-manager="currentTab.collection.groupManager"
                :image-size="currentTab.state.imageSize"
                :height="dimensions.height"
                :width="dimensions.width - 20"
                :properties="visibleProperties"
                :hide-if-modal="true"
                :selected-images="currentTab.collection.groupManager.selectedImages"
            />

            <div v-if="currentTab && currentTab.state.display == 'grid' && dimensions.width > 0" class="grid-container">
                <GridScroller
                    :tab="currentTab"
                    :manager="currentTab.collection.groupManager"
                    :height="dimensions.height - 15"
                    :width="dimensions.width - 32"
                    :selected-properties="visibleProperties"
                    class="p-0 m-0"
                    :show-images="true"
                    :selected-images="currentTab.collection.groupManager.selectedImages"
                />
            </div>

            <GraphView
                v-if="currentTab && currentTab.state.display == 'graph' && dimensions.height > 0"
                :collection="currentTab.collection"
                :height="dimensions.height - 15"
            />

            <MapView
                v-if="currentTab && currentTab.state.display == 'map' && tabStore.loaded"
                :tab="currentTab"
            />
        </div>
    </IslandPanel>
</template>

<style scoped>
.view-header-bar {
    display: flex;
    align-items: center;
    padding-left: var(--spacing-xs);
    background-color: var(--bg-secondary);
}

.view-container {
    flex: 1;
    min-width: 0;
    min-height: 0;
    overflow: hidden;
    padding-left: calc(var(--spacing-xs) + 0.23em);
}

.grid-container {
    height: 100%;
    overflow-y: hidden;
    overflow-x: overlay;
}

.tool-sm {
    color: rgb(0, 0, 0);
    line-height: 100%;
    padding: 5px;
    border-radius: 5px;
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    justify-content: center;
}

.tool:hover,
.tool-sm:hover {
    background-color: rgba(137, 176, 205, 0.4);
}

.selected,
.selected:hover {
    color: rgb(255, 255, 255);
    background-color: #384955;
}
</style>
