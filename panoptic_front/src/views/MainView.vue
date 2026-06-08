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
import TabProvider from '@/components/layoutpanels/TabProvider.vue'
import { useProjectStore } from '@/data/projectStore'
import { usePanopticStore } from '@/data/panopticStore'
import { useUiStore } from '@/data/uiStore'
import { useTabStore } from '@/data/tabStore'

const project = useProjectStore()
const panoptic = usePanopticStore()
const uiStore = useUiStore()
const tabStore = useTabStore()
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
    <AppShellLayout :gap="6" :activity-width="30" :toolbar-height="30" :status-height="0">
        <!-- Top toolbar (on canvas) -->
        <template #toolbar>
            <TopBarPanel />
        </template>

        <!-- Left activity bar (on canvas) -->
        <template #activity>
            <LeftBarPanel />
        </template>

        <!-- Islands work area - only show when uiStore has loaded -->
        <template v-if="uiStore.loaded && tabStore.loaded">
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
                    :secondary-ratio="uiStore.resizeStates.foldersHeight"
                    @update:secondary-ratio="(r) => { console.log('[MainView] Folders resized to:', r); uiStore.resizeStates.foldersHeight = r }"
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
                    <!-- Tab bar island (shared, never split) -->
                    <TabPanel />

                    <!-- 1 or 2 view islands, each its own card with a gap between.
                         Split state (shown/ratio) lives on the tab (Pillar F/Q13);
                         TabProvider remounts the panes on tab switch (Pillar D). -->
                    <TabProvider v-slot="{ tab }">
                        <SplitLayout
                            class="view-split"
                            direction="row"
                            :secondary-ratio="tab.state.splitRatio"
                            @update:secondary-ratio="(r) => { tab.state.splitRatio = r }"
                            :gap="10"
                            resizable
                            :min-primary="200"
                            :min-secondary="200"
                            :hide-secondary="!tab.state.splitView"
                        >
                            <template #primary>
                                <ViewPanel :view-index="0" />
                            </template>
                            <template #secondary>
                                <ViewPanel :view-index="1" />
                            </template>
                        </SplitLayout>
                    </TabProvider>
                </div>
            </template>
        </SidebarLayout>
        </template>
    </AppShellLayout>
    <div id="popup" style="position: fixed; top:0;left: 0; z-index: 9990;"></div>
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

</style>
