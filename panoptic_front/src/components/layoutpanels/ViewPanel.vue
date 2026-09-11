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
import RecommendView from '@/components/layoutpanels/RecommendView.vue'
import GroupView from '@/components/layoutpanels/GroupView.vue'
import wTT from '@/components/tooltips/withToolTip.vue'
import { useCurrentTab } from '@/data/useCurrentTab'

const props = defineProps<{
    viewIndex: number
}>()

const tab = useCurrentTab()
const view = computed(() => tab.value?.state.views[props.viewIndex] ?? null)
// The collection this pane renders (M4): may differ from the other pane's.
const collection = computed(() => tab.value?.collectionForView(props.viewIndex) ?? null)

// The group view was previously named "cluster"; views persisted before the rename still
// carry that type, so both values map to it.
const isGroupView = computed(() => view.value?.type == 'group' || view.value?.type == 'cluster')

function toggleProperties() {
    if (!view.value) return
    view.value.showProperties = !view.value.showProperties
}

// Switch this pane to the reco view, targeting the clicked group. Remember the
// current view type so the reco close button can restore it.
function openReco(groupId: number) {
    if (!tab.value || !view.value) return
    view.value.recoOptions.selectedGroupId = groupId
    view.value.recoOptions.previousType = view.value.type
    tab.value.setViewType(props.viewIndex, 'reco')
}

// Close the reco view, restoring the view type it was opened from (or tree).
function closeReco() {
    if (!tab.value || !view.value) return
    tab.value.setViewType(props.viewIndex, view.value.recoOptions.previousType ?? 'tree')
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
                <button class="tab-tool" :title="view.showProperties ? 'Hide properties' : 'Show properties'"
                    @click="toggleProperties">
                    <i :class="view.showProperties ? 'bi bi-eye' : 'bi bi-eye-slash'"></i>
                </button>

                <div class="flex-grow-1"></div>

                <!-- Toggle split view -->
                <wTT :message="tab?.state.splitView ? 'main.nav.unsplit_view' : 'main.nav.split_view'" pos="bottom">
                    <button class="tab-tool" :class="{ active: tab?.state.splitView }"
                        @click="tab && (tab.state.splitView = !tab.state.splitView)">
                        <i class="bi bi-columns"></i>
                    </button>
                </wTT>
            </div>
        </template>

        <div ref="containerRef" class="view-container">
            <div v-if="tab && view && collection && view.type == 'tree' && dimensions.width > 0"
                style="padding-left: 0.45rem">
                <TreeScroller input-key="view-panel-tree" :manager="collection" :image-size="view.imageSize"
                    :height="dimensions.height" :width="dimensions.width"
                    :properties="view.showProperties ? visibleProperties : []" :hide-if-modal="true" @reco="openReco" />

            </div>

            <div v-if="tab && view && collection && view.type == 'grid' && dimensions.width > 0" class="grid-container">
                <GridScroller :tab="tab" :image-size="view.imageSize" :manager="collection" :height="dimensions.height"
                    :width="dimensions.width" :selected-properties="view.showProperties ? visibleProperties : []"
                    class="p-0 m-0" :show-images="true" />
            </div>

            <div v-if="tab && view && collection && view.type == 'graph' && dimensions.height > 0"
                style="padding-left: 0.45rem; padding-top: var(--spacing-xs);">
                <GraphView :collection="collection" :height="dimensions.height - 15" :view="view" />
            </div>
            <MapView v-if="tab && view && collection && view.type == 'map'" :collection="collection"
                :map-options="view.mapOptions" :image-size="view.imageSize" />

            <div v-if="tab && view && collection && view.type == 'reco' && dimensions.width > 0"
                style="padding-left: 0.45rem">
                <RecommendView :tab="tab" :collection="collection" :reco-options="view.recoOptions"
                    :image-size="view.imageSize"
                    :width="dimensions.width - 32" :height="dimensions.height - 15" @close="closeReco" />
            </div>

            <div v-if="tab && view && collection && isGroupView && dimensions.width > 0" style="padding-left: 0.45rem">
                <GroupView :tab="tab" :collection="collection" :cluster-options="view.clusterOptions"
                    :image-size="view.imageSize"
                    :properties="view.showProperties ? visibleProperties : []" :width="dimensions.width"
                    :height="dimensions.height - 15" />
            </div>

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
    /* Same inset as FilterPanel's .filter-row, so the scroller's content edges line up
       with the filter row above it inside the identically-sized island bodies. */
    padding: 0 0px;
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
