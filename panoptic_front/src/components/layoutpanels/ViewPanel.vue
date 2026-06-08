<script setup lang="ts">
// A single view island root node — wraps the image visualisation in a growing
// island card. Used once per pane in the center view split. Each pane renders
// one of the tab's views (Pillar F): its own type + imageSize + mapOptions.
import { computed, onMounted, onUnmounted, ref } from 'vue'
import IslandPanel from '@/layouts/IslandPanel.vue'
import RangeInput from '@/components/inputs/RangeInput.vue'
import ViewSelectionDropdown from '@/components/layoutpanels/ViewSelectionDropdown.vue'
import TreeScroller from '@/components/scrollers/tree/TreeScroller.vue'
import GridScroller from '@/components/scrollers/grid/GridScroller.vue'
import GraphView from '@/components/graphview/GraphView.vue'
import MapView from '@/components/mapview/MapView.vue'
import FilterPanel from '@/components/layoutpanels/FilterPanel.vue'
import wTT from '@/components/tooltips/withToolTip.vue'
import { useCurrentTab } from '@/data/useCurrentTab'

const props = defineProps<{
    viewIndex: number
}>()

const tab = useCurrentTab()
const view = computed(() => tab.value?.state.views[props.viewIndex] ?? null)
// The collection this pane renders (M4): may differ from the other pane's.
const collection = computed(() => tab.value?.collectionForView(props.viewIndex) ?? null)

const containerRef = ref<HTMLElement>()
const dimensions = ref({ width: 0, height: 0 })
const visibleProperties = computed(() => tab.value?.getVisibleProperties() ?? [])

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
            <div class="view-header-bar" v-if="view">
                <!-- View type selection dropdown -->
                <ViewSelectionDropdown :view-index="props.viewIndex" />

                <!-- Image size range -->
                <div class="ms-3 d-flex align-items-center">
                    <wTT message="main.menu.image_size_tooltip" :click="false">
                        <div class="bi bi-aspect-ratio me-1"></div>
                    </wTT>
                    <RangeInput :min="30" :max="500" v-model="view.imageSize" />
                </div>

                <div class="flex-grow-1"></div>
            </div>
        </template>

        <!-- Per-view filter row (M4): controls this pane's collection. -->
        <FilterPanel v-if="view" :view-index="props.viewIndex" />

        <div ref="containerRef" class="view-container">
            <TreeScroller
                v-if="tab && view && collection && view.type == 'tree' && dimensions.width > 0"
                input-key="view-panel-tree"
                :group-manager="collection.groupManager"
                :image-size="view.imageSize"
                :height="dimensions.height"
                :width="dimensions.width - 20"
                :properties="visibleProperties"
                :hide-if-modal="true"
            />

            <div v-if="tab && view && collection && view.type == 'grid' && dimensions.width > 0" class="grid-container">
                <GridScroller
                    :tab="tab"
                    :image-size="view.imageSize"
                    :manager="collection.groupManager"
                    :height="dimensions.height - 15"
                    :width="dimensions.width - 32"
                    :selected-properties="visibleProperties"
                    class="p-0 m-0"
                    :show-images="true"
                />
            </div>

            <GraphView
                v-if="tab && view && collection && view.type == 'graph' && dimensions.height > 0"
                :collection="collection"
                :height="dimensions.height - 15"
            />

            <MapView
                v-if="tab && view && collection && view.type == 'map'"
                :tab="tab"
                :collection="collection"
                :map-options="view.mapOptions"
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
