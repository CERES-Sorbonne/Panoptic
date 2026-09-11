<script setup lang="ts">
import { computed, ref } from 'vue'
import PropertyIcon from '../properties/PropertyIcon.vue'
import { deletedID, PropertyType, PropertyGroupId } from '@/data/models'
import TextInput from './TextInput.vue'
import { useDataStore } from '@/data/dataStore'
import { useUiStore } from '@/data/uiStore'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const data = useDataStore()
const uiStore = useUiStore()

interface Props {
    ignoreIds?: number[]
    acceptableTypes?: PropertyType[] | null
    modelValue?: any
}

const props = defineProps<Props>()
const emits = defineEmits<{
    (e: 'select', id: number): void
}>()

const propertyFilter = ref('')

const groupOpen = uiStore.panelStates.propertySelectionExpansions

const propertyGroups = computed(() => data.propertyTree)

function getGroupName(groupId: number): string {
    if (groupId === PropertyGroupId.DEFAULT) return t('common.properties.default')
    if (groupId === PropertyGroupId.METADATA) return t('common.properties.metadata')
    const groupData = data.propertyGroups[groupId]
    if (groupData) return groupData.name
    return 'Unknown'
}

function isGroupOpen(groupId: number): boolean {
    if (propertyFilter.value) return true
    if (groupOpen[groupId] === undefined) return true
    return groupOpen[groupId]
}

function toggleGroup(groupId: number) {
    groupOpen[groupId] = !groupOpen[groupId]
}

function isPropertyVisible(propId: number, filter: string): boolean {
    const prop = data.properties[propId]
    if (!prop || prop.id === deletedID) return false
    if (props.ignoreIds?.includes(prop.id)) return false
    if (props.acceptableTypes && props.acceptableTypes.length > 0) {
        if (!props.acceptableTypes.includes(prop.type)) return false
    }
    if (filter && !prop.name.toLocaleLowerCase().includes(filter)) return false
    return true
}

const filteredGroups = computed(() => {
    const filter = propertyFilter.value.toLocaleLowerCase()
    const result = []
    for (const group of propertyGroups.value) {
        const propertyIds = group.propertyIds.filter(id => isPropertyVisible(id, filter))
        if (propertyIds.length === 0) continue
        result.push({ groupId: group.groupId, propertyIds })
    }
    return result
})

</script>

<template>
    <div class="flex flex-column h-100">
        <div class="p-1">
            <TextInput v-model="propertyFilter" :focus="true" />
        </div>
        <div class="flex-grow-1 overflow-auto pb-1" style="max-height: 350px; overflow-y: auto;">
            <template v-for="group in filteredGroups" :key="group.groupId">
                <div class="group-header" @click="toggleGroup(group.groupId)">
                    <i class="expand-icon" :class="isGroupOpen(group.groupId) ? 'bi bi-chevron-down' : 'bi bi-chevron-right'"></i>
                    <span class="group-name">{{ getGroupName(group.groupId) }}</span>
                </div>
                <template v-if="isGroupOpen(group.groupId)">
                    <div
                        v-for="propId in group.propertyIds"
                        :key="propId"
                        class="property-item base-hover text-black"
                        style="cursor:pointer"
                        @click="emits('select', propId)"
                    >
                        <PropertyIcon :type="data.properties[propId].type" class="me-2" />
                        <span>{{ data.properties[propId].name }}</span>
                    </div>
                </template>
            </template>
        </div>
    </div>
</template>

<style scoped>
.group-header,
.property-item {
    border: none;
    box-shadow: none;
}

.group-header {
    display: flex;
    align-items: center;
    gap: 4px;
    height: 24px;
    margin: 4px 4px 0;
    padding: 0 var(--spacing-xs);
    cursor: pointer;
    white-space: nowrap;
    background: none;
    border-radius: 4px;
}

.group-header:hover {
    background-color: var(--hover-bg);
}

.expand-icon {
    width: 14px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    color: var(--text-tertiary);
    flex-shrink: 0;
}

.group-name {
    color: var(--text-secondary);
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-semibold);
    text-transform: capitalize;
    overflow: hidden;
    text-overflow: ellipsis;
}

.property-item {
    display: flex;
    align-items: center;
    height: 26px;
    margin: 0 4px;
    padding: 0 var(--spacing-xs) 0 18px;
    border-radius: 4px;
    background: none;
}

.property-item:hover {
    background-color: var(--hover-bg);
}
</style>
