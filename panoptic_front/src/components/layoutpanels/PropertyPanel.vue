<script setup lang="ts">
// Properties / Export tool-window root node — inserted into the sidebar
// split's #secondary. Shows either the property list or the export actions
// depending on which bottom panel is active.
import IslandPanel from '@/layouts/IslandPanel.vue'
import TabContainer from '@/components/TabContainer.vue'
import PropertyGroupPanel from './PropertyGroupPanel.vue'
import { useUiStore } from '@/data/uiStore'
import { useTabStore } from '@/data/tabStore'
import { useDataStore } from '@/data/dataStore'
import { usePanopticStore } from '@/data/panopticStore'
import { ModalId } from '@/data/models'
import { goNext } from '@/utils/utils'

const uiStore = useUiStore()
const tabStore = useTabStore()
const data = useDataStore()
const panoptic = usePanopticStore()

const isPropertiesPanel = uiStore.panelStates.activeBottomPanel === 'properties'
</script>

<template>
    <IslandPanel grow>
        <template #header>
            <div class="tw-header">
                <span class="tw-title">{{ uiStore.panelStates.activeBottomPanel === 'export' ? 'Export' : 'Properties' }}</span>
                <div class="tw-actions">
                    <button v-if="isPropertiesPanel" class="tw-action" title="Add property"
                        @click="panoptic.showModal(ModalId.PROPERTY); goNext()">
                        <i class="bi bi-plus-lg"></i>
                    </button>
                    <button v-if="isPropertiesPanel" class="tw-action" title="Add group"
                        @click="data.addPropertyGroup('New Group')">
                        <i class="bi bi-plus-lg"></i>
                    </button>
                    <button class="tw-action" title="Options"><i class="bi bi-three-dots"></i></button>
                    <button class="tw-action" title="Hide" @click="uiStore.panelStates.activeBottomPanel = null"><i class="bi bi-dash"></i></button>
                </div>
            </div>
        </template>
        <div class="tw-body">
            <template v-if="uiStore.panelStates.activeBottomPanel === 'export'">
                <button class="export-row" @click="uiStore.panelStates.activeBottomPanel = null">
                    <i class="export-icon bi bi-download"></i>
                    <span>Export as CSV</span>
                </button>
                <button class="export-row" @click="uiStore.panelStates.activeBottomPanel = null">
                    <i class="export-icon bi bi-download"></i>
                    <span>Export as JSON</span>
                </button>
                <button class="export-row" @click="uiStore.panelStates.activeBottomPanel = null">
                    <i class="export-icon bi bi-download"></i>
                    <span>Export images</span>
                </button>
            </template>
            <template v-else>
                <TabContainer :id="tabStore.mainTab">
                    <template #default="{ tab }">
                        <PropertyGroupPanel :tab="tab" />
                    </template>
                </TabContainer>
            </template>
        </div>
    </IslandPanel>
</template>

<style scoped>
/* Tool window header (shared pattern across panels) */
.tw-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 30px;
    padding: 0 var(--spacing-sm);
}

.tw-title {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-semibold);
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.02em;
}

.tw-actions {
    display: flex;
    gap: 2px;
}

.tw-action {
    width: 22px;
    height: 22px;
    background: none;
    border: none;
    border-radius: var(--radius-sm);
    color: var(--text-tertiary);
}

.tw-action:hover {
    background-color: var(--hover-bg);
    color: var(--text-primary);
}

.tw-body {
    flex: 1;
    min-height: 0;
    overflow: auto;
    padding: var(--spacing-xs) 0;
}

/* Export list */
.export-row {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
    width: 100%;
    height: 30px;
    padding: 0 var(--spacing-sm);
    background: none;
    border: none;
    text-align: left;
    color: var(--text-primary);
    font-size: var(--font-size-sm);
    transition: background-color var(--transition-fast);
}

.export-row:hover {
    background-color: var(--hover-bg);
}

.export-icon {
    font-size: var(--font-size-sm);
    color: var(--text-secondary);
}
</style>
