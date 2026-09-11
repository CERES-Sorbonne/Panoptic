<script setup lang="ts">
// Properties tool-window root node — inserted into the sidebar split's
// #secondary. Export is a modal (ExportModal2), not a panel.
import IslandPanel from '@/layouts/IslandPanel.vue'
import TabContainer from '@/components/TabContainer.vue'
import PropertyGroupPanel from './PropertyGroupPanel.vue'
import wTT from '@/components/tooltips/withToolTip.vue'
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
                <span class="tw-title">{{ $t('main.nav.properties.title') }}</span>
                <div class="tw-actions">
                    <wTT message="main.nav.properties.add_property" pos="bottom">
                        <button class="tw-action" @click="panoptic.showModal(ModalId.PROPERTY); goNext()">
                            <i class="bi bi-plus-lg"></i>
                        </button>
                    </wTT>
                    <wTT message="main.nav.properties.add_property_group" pos="bottom">
                        <button class="tw-action" @click="data.addPropertyGroup('New Group')">
                            <i class="bi bi-folder-plus"></i>
                        </button>
                    </wTT>
                    <wTT message="main.nav.hide_panel" pos="bottom">
                        <button class="tw-action" @click="uiStore.panelStates.activeBottomPanel = null"><i class="bi bi-dash"></i></button>
                    </wTT>
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
    padding: 0 2px 0 var(--spacing-sm);
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
