<script setup lang="ts">
import { computed, onMounted } from 'vue'
import router from '@/router'
import AppShellLayout from '@/layouts/AppShellLayout.vue'
import SidebarLayout from '@/layouts/SidebarLayout.vue'
import SplitLayout from '@/layouts/SplitLayout.vue'
import TopBarPanel from '@/components/layoutpanels/TopBarPanel.vue'
import LeftBarPanel from '@/components/layoutpanels/LeftBarPanel.vue'
import FolderPanel from '@/components/layoutpanels/FolderPanel.vue'
import PropertyPanel from '@/components/layoutpanels/PropertyPanel.vue'
import TabPanel from '@/components/layoutpanels/TabPanel.vue'
import ViewPanel from '@/components/layoutpanels/ViewPanel.vue'
import { useProjectStore } from '@/data/projectStore'
import { usePanopticStore } from '@/data/panopticStore'
import { useUiStore } from '@/data/uiStore'

const project = useProjectStore()
const panoptic = usePanopticStore()
const uiStore = useUiStore()

const leftCollapsed = computed(() => !uiStore.panelStates.leftPanelOpen && uiStore.panelStates.activeBottomPanel === null)

onMounted(async () => {
    console.log('[MainView] Mounted, checking if project is loaded')
    if (!panoptic.isProjectLoaded) {
        console.log('[MainView] Project not loaded, redirecting to home')
        router.push('/')
        return
    }

    console.log('[MainView] Initializing project store and uiStore')
    await project.init()
    console.log('[MainView] Stores initialized, uiStore.loaded:', uiStore.loaded)
})
</script>

<template>
    <!-- Always show outer shell, but hide islands until uiStore loads -->
    <AppShellLayout :gap="6" :activity-width="40" :toolbar-height="40" :status-height="24">
        <!-- Top toolbar (on canvas) -->
        <template #toolbar>
            <TopBarPanel />
        </template>

        <!-- Left activity bar (on canvas) -->
        <template #activity>
            <LeftBarPanel />
        </template>

        <!-- Status bar (flush on canvas) -->
        <template #statusbar>
            <div class="status">
                <span class="status-item">panoptic_back</span>
                <span class="status-spacer"></span>
                <span class="status-item">52:23</span>
                <span class="status-item">LF</span>
                <span class="status-item">UTF-8</span>
                <span class="status-item">4 spaces</span>
                <span class="status-item">Python 3.13</span>
            </div>
        </template>

        <!-- Islands work area - only show when uiStore has loaded -->
        <template v-if="uiStore.loaded">
        <SidebarLayout
            :sidebar-width="uiStore.resizeStates.leftSidebarWidth"
            @update:sidebar-width="(w) => { console.log('[MainView] Sidebar resized to:', w); uiStore.resizeStates.leftSidebarWidth = w }"
            :gap="6"
            resizable
            :min-width="180"
            :max-width="500"
            :collapsed="leftCollapsed"
        >
            <!-- Left side: Folders (top) over Properties (bottom). Either pane
                 can be hidden, and the divider between them is draggable. -->
            <template #sidebar>
                <SplitLayout
                    direction="column"
                    :secondary-size="uiStore.resizeStates.foldersHeight"
                    @update:secondary-size="(h) => { console.log('[MainView] Folders resized to:', h); uiStore.resizeStates.foldersHeight = h }"
                    :gap="6"
                    resizable
                    :min-primary="100"
                    :min-secondary="90"
                    :hide-primary="!uiStore.panelStates.leftPanelOpen"
                    :hide-secondary="uiStore.panelStates.activeBottomPanel === null"
                >
                    <template #primary>
                        <FolderPanel />
                    </template>
                    <template #secondary>
                        <PropertyPanel />
                    </template>
                </SplitLayout>
            </template>

            <!-- Center: a tab/filter island, then 1 or 2 separate view islands -->
            <template #main>
                <div class="center-stack">
                    <!-- Tab bar + filter zone island (shared, never split) -->
                    <TabPanel />

                    <!-- 1 or 2 view islands, each its own card with a gap between -->
                    <SplitLayout
                        class="view-split"
                        direction="row"
                        :secondary-size="uiStore.resizeStates.mainSplitWidth"
                        @update:secondary-size="(w) => { console.log('[MainView] Split resized to:', w); uiStore.resizeStates.mainSplitWidth = w }"
                        :gap="10"
                        resizable
                        :min-primary="200"
                        :min-secondary="200"
                        :hide-secondary="!uiStore.panelStates.viewSplitEnabled"
                    >
                        <template #primary>
                            <ViewPanel />
                        </template>
                        <template #secondary>
                            <ViewPanel />
                        </template>
                    </SplitLayout>
                </div>
            </template>
        </SidebarLayout>
        </template>
    </AppShellLayout>
</template>

<style scoped>
/* Center column: tab/filter island stacked over the view island(s) */
.center-stack {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-width: 0;
    min-height: 0;
    gap: var(--island-gap);
}

/* View split fills the full width of the center column. */
.view-split {
    width: 100%;
}

/* ===== Status bar content ===== */
.status {
    display: flex;
    align-items: center;
    gap: var(--spacing-md);
    flex: 1;
    padding: 0 var(--spacing-md);
    font-size: var(--font-size-xs);
    color: var(--text-secondary);
}

.status-spacer {
    flex: 1;
}

.status-item {
    white-space: nowrap;
}
</style>
