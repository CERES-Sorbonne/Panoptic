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
import RecoWorkspace from '@/components/layoutpanels/RecoWorkspace.vue'
import wTT from '@/components/tooltips/withToolTip.vue'
import { useCurrentTab } from '@/data/useCurrentTab'

const props = defineProps<{
    viewIndex: number
}>()

const tab = useCurrentTab()
const view = computed(() => tab.value?.state.views[props.viewIndex] ?? null)
// The collection this pane renders (M4): may differ from the other pane's.
const collection = computed(() => tab.value?.collectionForView(props.viewIndex) ?? null)

function toggleProperties() {
    if (!view.value) return
    view.value.showProperties = !view.value.showProperties
}

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

                <!-- Toggle properties visibility -->
                <button class="tab-tool" :title="view.showProperties ? 'Hide properties' : 'Show properties'" @click="toggleProperties">
                    <i :class="view.showProperties ? 'bi bi-eye' : 'bi bi-eye-slash'"></i>
                </button>

                <div class="flex-grow-1"></div>

                <!-- Toggle split view -->
                <button class="tab-tool" :class="{ active: tab?.state.splitView }" :title="tab?.state.splitView ? 'Unsplit' : 'Split right'" @click="tab && (tab.state.splitView = !tab.state.splitView)">
                    <i class="bi bi-columns"></i>
                </button>
            </div>
        </template>

        <div ref="containerRef" class="view-container">
            <TreeScroller
                v-if="tab && view && collection && view.type == 'tree' && dimensions.width > 0"
                input-key="view-panel-tree"
                :group-manager="collection.groupManager"
                :image-size="view.imageSize"
                :height="dimensions.height"
                :width="dimensions.width - 20"
                :properties="view.showProperties ? visibleProperties : []"
                :hide-if-modal="true"
            />

            <div v-if="tab && view && collection && view.type == 'grid' && dimensions.width > 0" class="grid-container">
                <GridScroller
                    :tab="tab"
                    :image-size="view.imageSize"
                    :manager="collection.groupManager"
                    :height="dimensions.height - 15"
                    :width="dimensions.width - 32"
                    :selected-properties="view.showProperties ? visibleProperties : []"
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

            <RecoWorkspace
                v-if="tab && view && collection && view.type == 'reco' && dimensions.width > 0"
                :tab="tab"
                :collection="collection"
                :reco-options="view.recoOptions"
                :image-size="view.imageSize"
                :width="dimensions.width - 32"
                :height="dimensions.height - 15"
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

/* Compact, borderless icon button for the properties toggle eye. */
.tab-tool {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    border: none !important;
    background: none;
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    font-size: 14px;
    line-height: 1;
    cursor: pointer;
    transition: background-color var(--transition-fast), color var(--transition-fast);
}

.tab-tool:hover {
    background-color: var(--hover-bg);
    color: var(--text-primary);
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
