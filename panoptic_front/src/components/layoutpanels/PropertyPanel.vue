<script setup lang="ts">
// Properties tool-window root node — inserted into the sidebar split's
// #secondary. Export is a modal (ExportModal2), not a panel.
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

</script>

<template>
    <IslandPanel grow>
        <template #header>
            <div class="tw-header">
                <span class="tw-title">Properties</span>
                <div class="tw-actions">
                    <button class="tw-action" title="Add property"
                        @click="panoptic.showModal(ModalId.PROPERTY); goNext()">
                        <i class="bi bi-plus-lg"></i>
                    </button>
                    <button class="tw-action" title="Add group"
                        @click="data.addPropertyGroup('New Group')">
                        <i class="bi bi-plus-lg"></i>
                    </button>
                    <button class="tw-action" title="Options"><i class="bi bi-three-dots"></i></button>
                    <button class="tw-action" title="Hide" @click="uiStore.panelStates.activeBottomPanel = null"><i class="bi bi-dash"></i></button>
                </div>
            </div>
        </template>
        <div class="tw-body">
            <TabContainer :id="tabStore.mainTab">
                <template #default="{ tab }">
                    <PropertyGroupPanel :tab="tab" />
                </template>
            </TabContainer>
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

</style>
