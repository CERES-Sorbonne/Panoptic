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
import FilterIsland from '@/components/layoutpanels/FilterIsland.vue'
import ViewPanel from '@/components/layoutpanels/ViewPanel.vue'
import TabProvider from '@/components/layoutpanels/TabProvider.vue'
import { useProjectStore } from '@/data/projectStore'
import { usePanopticStore } from '@/data/panopticStore'
import { useUiStore } from '@/data/uiStore'
import { useTabStore } from '@/data/tabStore'
import { ModalId } from '@/data/models'
import PropertyModal from '@/components/modals/PropertyModal.vue'
import FolderSelectionModal from '@/components/modals/FolderSelectionModal.vue'
import ExportModal2 from '@/components/modals/ExportModal2.vue'
import ImageModal from '@/components/modals/ImageModal.vue'
import ImageZoomModal from '@/components/modals/ImageZoomModal.vue'
import SettingsModal from '@/components/modals/SettingsModal.vue'
import ImportModal from '@/components/modals/ImportModal.vue'
import FileSourceModal from '@/components/modals/FileSourceModal.vue'
import TagModal from '@/components/modals/TagModal.vue'
import FirstModal from '@/components/modals/FirstModal.vue'
import NotifModal from '@/components/modals/NotifModal.vue'
import SelectionModal from '@/components/modals/SelectionModal.vue'

const project = useProjectStore()
const panoptic = usePanopticStore()
const uiStore = useUiStore()
const tabStore = useTabStore()
const leftCollapsed = computed(() => !uiStore.panelStates.leftPanelOpen && uiStore.panelStates.activeBottomPanel === null)

onMounted(async () => {
    console.log('[ProjectView] Mounted, checking if project is loaded')
    if (!panoptic.isProjectLoaded) {
        console.log('[ProjectView] Project not loaded, redirecting to home')
        router.push('/')
        return
    }

    console.log('[ProjectView] Initializing project store and uiStore')
    await project.init()
    console.log('[ProjectView] Stores initialized, uiStore.loaded:', uiStore.loaded)
})
</script>

<template>
    <AppShellLayout :gap="6" :activity-width="32" :toolbar-height="32" :status-height="0">
        <!-- Top toolbar -->
        <template #toolbar>
            <TopBarPanel />
        </template>

        <!-- Left activity bar -->
        <template #activity>
            <LeftBarPanel />
        </template>

        <!-- Work area -->
        <template v-if="uiStore.loaded && tabStore.loaded">
        <SidebarLayout
            :sidebar-width="uiStore.resizeStates.leftSidebarWidth"
            @update:sidebar-width="(w) => { console.log('[ProjectView] Sidebar resized to:', w); uiStore.resizeStates.leftSidebarWidth = w }"
            :gap="6"
            resizable
            :min-width="180"
            :max-width="500"
            :collapsed="leftCollapsed"
        >
            <!-- Folders over properties, resizable divider -->
            <template #sidebar>
                <SplitLayout
                    direction="column"
                    :secondary-ratio="uiStore.resizeStates.foldersHeight"
                    @update:secondary-ratio="(r) => { console.log('[ProjectView] Folders resized to:', r); uiStore.resizeStates.foldersHeight = r }"
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

            <!-- Center: filter bar above the views -->
            <template #main>
                <div class="center-stack">
                    <!-- Filter bar -->
                    <FilterIsland />

                    <!-- One or two views, side by side when split -->
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
    <PropertyModal :id="ModalId.PROPERTY" />
    <FolderSelectionModal :id="ModalId.FOLDERSELECTION" />
    <ExportModal2 />
    <ImageModal />
    <ImageZoomModal />
    <SettingsModal />
    <ImportModal />
    <FileSourceModal />
    <TagModal />
    <FirstModal />
    <NotifModal />
    <SelectionModal />
</template>

<style scoped>
/* Center column: filter bar above the views */
.center-stack {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-width: 0;
    min-height: 0;
    gap: var(--island-gap);
}

/* View split fills the center column */
.view-split {
    width: 100%;
}

</style>
