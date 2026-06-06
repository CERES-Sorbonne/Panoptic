<script setup lang="ts">
import { computed } from 'vue'
import wTT from '@/components/tooltips/withToolTip.vue'
import Dropdown from '@/components/dropdowns/Dropdown.vue'
import { useTabStore } from '@/data/tabStore'

const tabStore = useTabStore()
const currentTab = computed(() => tabStore.getMainTab())

interface ViewOption {
    id: string
    icon: string
    tooltip: string
}

const viewOptions: ViewOption[] = [
    { id: 'tree', icon: 'grid-3x3-gap-fill', tooltip: 'main.menu.grid_tooltip' },
    { id: 'grid', icon: 'table', tooltip: 'main.menu.table_tooltip' },
    { id: 'graph', icon: 'bar-chart', tooltip: 'main.menu.graph_tooltip' },
    { id: 'map', icon: 'map', tooltip: 'main.menu.map_tooltip' },
]

const currentView = computed(() => {
    return currentTab.value?.state.display ?? 'grid'
})

const activeOption = computed(() => {
    return viewOptions.find(opt => opt.id === currentView.value) ?? viewOptions[0]
})

function selectView(viewId: string) {
    if (currentTab.value) {
        currentTab.value.setViewMode(viewId)
    }
}

</script>

<template>
    <Dropdown placement="bottom-start" class="view-selection-dropdown">
        <template #button>
            <div class="view-button" :class="{ active: currentView === activeOption.id }">
                <wTT :message="activeOption.tooltip">
                    <i :class="'bi bi-' + activeOption.icon"></i>
                </wTT>
            </div>
        </template>

        <template #popup="{ hide }">
            <div class="view-popup">
                <div
                    v-for="opt in viewOptions"
                    :key="opt.id"
                    class="view-popup-item"
                    :class="{ 'is-selected': currentView === opt.id }"
                    @click="selectView(opt.id); hide()"
                >
                    <span v-if="opt.icon" :class="'bi bi-' + opt.icon" class="me-2"></span>
                    <wTT :message="opt.tooltip">
                        {{ opt.id.charAt(0).toUpperCase() + opt.id.slice(1) }}
                    </wTT>
                </div>
            </div>
        </template>
    </Dropdown>
</template>

<style scoped>
.view-selection-dropdown {
    display: inline-flex;
}

.view-button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 26px;
    height: 26px;
    background: none;
    border: none;
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    cursor: pointer;
    transition: background-color var(--transition-fast);
}

.view-button:hover {
    background-color: var(--hover-bg);
    color: var(--text-primary);
}

.view-popup {
    display: flex;
    flex-direction: column;
}

.view-popup-item {
    display: inline-flex;
    align-items: center;
    padding: 4px 8px;
    cursor: pointer;
    transition: background-color var(--transition-fast);
    white-space: nowrap;
}

.view-popup-item:hover {
    background-color: var(--hover-bg);
}

.view-popup-item.is-selected {
    color: var(--primary);
    font-weight: var(--font-weight-medium);
}
</style>
