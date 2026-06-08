<script setup lang="ts">
import { PropertyGroupId, PropertyGroupNode } from '@/data/models'
import { TabManager } from '@/core/TabManager'
import PropertyRow from './PropertyRow.vue'
import { computed } from 'vue'
import { useDataStore } from '@/data/dataStore'
import { useUiStore } from '@/data/uiStore'
import { usePanopticStore } from '@/data/panopticStore'
import { goNext } from '@/utils/utils'

const data = useDataStore()
const uiStore = useUiStore()
const panoptic = usePanopticStore()
const props = defineProps<{
    tab: TabManager
}>()

const groupOpen = uiStore.panelStates.groupExpansions

const visibleGroups = computed(() => {
    return data.propertyTree
})

function getGroupName(group: PropertyGroupNode): string {
    if (group.groupId === PropertyGroupId.DEFAULT) return 'Default'
    if (group.groupId === PropertyGroupId.METADATA) return 'Metadata'
    const groupData = data.propertyGroups[group.groupId]
    if (groupData) return groupData.name
    return 'Unknown'
}

function isAllVisible(group: PropertyGroupNode): boolean {
    if (group.propertyIds.length === 0) return false
    return group.propertyIds.every(id => props.tab.state.visibleProperties[id] === true)
}

function isNoneVisible(group: PropertyGroupNode): boolean {
    if (group.propertyIds.length === 0) return false
    return group.propertyIds.every(id => props.tab.state.visibleProperties[id] !== true)
}

function toggleGroupVisibility(group: PropertyGroupNode) {
    const allVisible = isAllVisible(group)
    props.tab.setVisibleProperties(group.propertyIds, !allVisible)
}

function toggleExpand(groupId: number) {
    groupOpen[groupId] = !groupOpen[groupId]
}

</script>

<template>
    <div v-for="group in visibleGroups" :key="group.groupId">
        <div class="group-header" @click="toggleExpand(group.groupId)">
            <i class="expand-icon" :class="groupOpen[group.groupId] ? 'bi bi-chevron-down' : 'bi bi-chevron-right'"></i>
            <span class="group-name">{{ getGroupName(group) }}</span>
            <span v-if="group.groupId !== PropertyGroupId.METADATA" class="add-prop-btn"
                @click.stop="panoptic.showModal(ModalId.PROPERTY); goNext()">
                <i class="bi bi-plus-lg"></i>
            </span>
            <span v-if="group.propertyIds.length > 0" class="visibility-toggle" @click.stop="toggleGroupVisibility(group)">
                <i :class="[
                    'bi bi-eye',
                    isAllVisible(group) ? 'text-primary' : 'text-secondary'
                ]"></i>
            </span>
        </div>
        <template v-if="groupOpen[group.groupId]">
            <PropertyRow 
                v-for="propId in group.propertyIds" 
                :key="propId"
                :property="data.properties[propId]" 
                :tab="props.tab" 
            />
        </template>
    </div>
</template>

<style scoped>
.group-header {
    display: flex;
    align-items: center;
    gap: 4px;
    height: 28px;
    padding: 0 var(--spacing-sm);
    cursor: pointer;
    white-space: nowrap;
    /* background-color: var(--border-solid); */
}

.group-header:hover {
    background-color: var(--border-alpha-40);
}

.expand-icon {
    width: 14px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: var(--font-size-xs);
    color: var(--text-tertiary);
    flex-shrink: 0;
}

.group-name {
    /* color: var(--text-secondary); */
    font-size: var(--font-size-sm);
    /* font-weight: var(--font-weight-semibold); */
    text-transform: capitalize;
    overflow: hidden;
    text-overflow: ellipsis;
}

.visibility-toggle {
    margin-left: auto;
    padding-left: 8px;
    cursor: pointer;
    flex-shrink: 0;
}

.add-prop-btn {
    margin-left: auto;
    padding-left: 8px;
    cursor: pointer;
    flex-shrink: 0;
    opacity: 0;
    transition: opacity var(--transition-fast);
}

.group-header:hover .add-prop-btn {
    opacity: 1;
}

.add-prop-btn:hover {
    color: var(--primary);
}

.text-primary {
    color: var(--primary) !important;
}

.text-secondary {
    color: var(--text-tertiary) !important;
}
</style>
