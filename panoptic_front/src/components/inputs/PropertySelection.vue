<script setup lang="ts">
import { computed, ref } from 'vue'
import PropertyIcon from '../properties/PropertyIcon.vue'
import { deletedID, PropertyType, PropertyGroupId } from '@/data/models'
import TextInput from './TextInput.vue'
import { useDataStore } from '@/data/dataStore'
import { useUiStore } from '@/data/uiStore'

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
    if (groupId === PropertyGroupId.DEFAULT) return 'Default'
    if (groupId === PropertyGroupId.METADATA) return 'Metadata'
    const groupData = data.propertyGroups[groupId]
    if (groupData) return groupData.name
    return 'Unknown'
}

function isGroupOpen(groupId: number): boolean {
    if (groupOpen[groupId] === undefined) return true
    return groupOpen[groupId]
}

function toggleGroup(groupId: number) {
    groupOpen[groupId] = !groupOpen[groupId]
}

const filteredGroupIds = computed(() => {
    const filter = propertyFilter.value.toLocaleLowerCase()
    if (!filter) return new Set(propertyGroups.value.map(g => g.groupId))

    const result = new Set<number>()
    for (const group of propertyGroups.value) {
        for (const propId of group.propertyIds) {
            const prop = data.properties[propId]
            if (prop && prop.id !== deletedID) {
                if (props.ignoreIds?.includes(prop.id)) continue
                if (props.acceptableTypes && props.acceptableTypes.length > 0) {
                    if (!props.acceptableTypes.includes(prop.type)) continue
                }
                if (prop.name.toLocaleLowerCase().includes(filter)) {
                    result.add(group.groupId)
                    break
                }
            }
        }
    }
    return result
})

</script>

<template>
    <div class="flex flex-column h-100">
        <div class="p-1 mb-1">
            <TextInput v-model="propertyFilter" :focus="true" />
        </div>
        <div class="flex-grow-1 overflow-auto" style="max-height: 350px; overflow-y: scroll;">
            <template v-for="group in propertyGroups" :key="group.groupId">
                <template v-if="filteredGroupIds.has(group.groupId)">
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
                            <PropertyIcon v-if="data.properties[propId] && data.properties[propId].id !== deletedID" :type="data.properties[propId].type" class="me-2" />
                            <span>{{ data.properties[propId]?.name }}</span>
                        </div>
                    </template>
                </template>
            </template>
        </div>
    </div>
</template>

<style scoped>
.group-header {
    display: flex;
    align-items: center;
    gap: 4px;
    height: 30px;
    padding: 0 var(--spacing-sm);
    cursor: pointer;
    white-space: nowrap;
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
    height: 30px;
    padding: 0 var(--spacing-sm);
}

.property-item:hover {
    background-color: var(--hover-bg);
}
</style>
