<script setup lang="ts">
import { computed, ref, watch, onMounted, nextTick } from 'vue'
import PropertyIcon from '../properties/PropertyIcon.vue'
import { deletedID, PropertyType, PropertyGroupId } from '@/data/models'
import { useDataStore } from '@/data/stores/dataStore'
import { useUiStore } from '@/data/stores/uiStore'
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


// keyboard navigation over the visible (flattened) items
const searchElem = ref<HTMLInputElement>(null)
const listElem = ref<HTMLElement>(null)
const activeIndex = ref(-1)
const flatIds = computed(() => filteredGroups.value
    .filter(g => isGroupOpen(g.groupId))
    .flatMap(g => g.propertyIds))

watch(propertyFilter, () => activeIndex.value = propertyFilter.value ? 0 : -1)

function move(delta: number) {
    const n = flatIds.value.length
    if (!n) return
    activeIndex.value = activeIndex.value < 0 ? (delta > 0 ? 0 : n - 1) : (activeIndex.value + delta + n) % n
    nextTick(() => listElem.value?.querySelector('.pp-item.active')?.scrollIntoView({ block: 'nearest' }))
}

function onEnter(e: KeyboardEvent) {
    const id = flatIds.value[activeIndex.value]
    if (id === undefined) return
    e.stopPropagation()
    emits('select', id)
}

onMounted(() => nextTick(() => searchElem.value?.focus()))
</script>

<template>
    <div class="prop-picker">
        <div class="prop-picker-search">
            <i class="bi bi-search"></i>
            <input ref="searchElem" v-model="propertyFilter" type="text" :placeholder="t('main.menu.search_short')"
                @keydown.down.prevent="move(1)" @keydown.up.prevent="move(-1)" @keydown.enter="onEnter" />
            <i v-if="propertyFilter" class="bi bi-x-lg clear" @click="propertyFilter = ''; searchElem?.focus()"></i>
        </div>
        <div ref="listElem" class="prop-picker-list">
            <template v-for="group in filteredGroups" :key="group.groupId">
                <div class="pp-group" @click="toggleGroup(group.groupId)">
                    <i class="expand-icon" :class="isGroupOpen(group.groupId) ? 'bi bi-chevron-down' : 'bi bi-chevron-right'"></i>
                    <span class="group-name">{{ getGroupName(group.groupId) }}</span>
                </div>
                <template v-if="isGroupOpen(group.groupId)">
                    <div v-for="propId in group.propertyIds" :key="propId" class="pp-item"
                        :class="{ active: flatIds[activeIndex] === propId, selected: props.modelValue === propId }"
                        @mousemove="activeIndex = flatIds.indexOf(propId)"
                        @click="emits('select', propId)">
                        <PropertyIcon :type="data.properties[propId].type" class="item-icon" />
                        <span class="item-name">{{ data.properties[propId].name }}</span>
                    </div>
                </template>
            </template>
            <div v-if="!filteredGroups.length" class="empty">—</div>
        </div>
    </div>
</template>

<style scoped>
.prop-picker {
    display: flex;
    flex-direction: column;
    min-width: 220px;
    font-size: 14px;
}

.prop-picker-search {
    display: flex;
    align-items: center;
    gap: 8px;
    height: 36px;
    padding: 0 12px;
    border-bottom: 1px solid var(--border-light);
    color: var(--text-tertiary);
}

.prop-picker-search input {
    flex: 1;
    min-width: 0;
    border: none;
    outline: none;
    background: transparent;
    padding: 0;
    font-size: 14px;
    color: var(--text-primary, #212529);
}

.prop-picker-search input::placeholder {
    color: var(--text-tertiary);
}

.prop-picker-search .clear {
    font-size: 11px;
    cursor: pointer;
}

.prop-picker-search .clear:hover {
    color: var(--text-secondary);
}

.prop-picker-list {
    max-height: 360px;
    overflow-y: auto;
    padding: 6px;
}

.pp-group {
    display: flex;
    align-items: center;
    gap: 4px;
    height: 24px;
    padding: 0 6px;
    margin-top: 4px;
    cursor: pointer;
    white-space: nowrap;
    border-radius: 6px;
    user-select: none;
}

.pp-group:first-child {
    margin-top: 0;
}

.pp-group:hover .group-name,
.pp-group:hover .expand-icon {
    color: var(--text-secondary);
}

.expand-icon {
    width: 12px;
    font-size: 10px;
    color: var(--text-tertiary);
    flex-shrink: 0;
}

.group-name {
    color: var(--text-tertiary);
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    overflow: hidden;
    text-overflow: ellipsis;
}

.pp-item {
    display: flex;
    align-items: center;
    gap: 8px;
    height: 28px;
    padding: 0 8px 0 22px;
    border-radius: 6px;
    cursor: pointer;
    white-space: nowrap;
    color: var(--text-primary, #212529);
}

.pp-item.active {
    background-color: var(--hover-bg);
}

.pp-item.selected {
    background-color: var(--primary-light);
    color: var(--primary);
}

.item-icon {
    width: 16px;
    flex-shrink: 0;
    display: inline-flex;
    justify-content: center;
}

.item-name {
    overflow: hidden;
    text-overflow: ellipsis;
}

.empty {
    padding: 6px 8px;
    color: var(--text-tertiary);
}
</style>
