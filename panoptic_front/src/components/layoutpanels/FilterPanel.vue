<script setup lang="ts">
// Per-view filter row — bind toggle, instance/image mode, text search, filter,
// group, sort. Rendered inside each ViewPanel (M4) and bound to that view's
// collection, so split views can filter independently. The bind toggle shares /
// splits the collection between the two views.
import { computed } from 'vue'
import TextSearchInput from '@/components/inputs/TextSearchInput.vue'
import FilterForm from '@/components/forms/FilterForm.vue'
import GroupForm from '@/components/forms/GroupForm.vue'
import SortForm from '@/components/forms/SortForm.vue'
import ImageInstanceDropdown from '@/components/layoutpanels/ImageInstanceDropdown.vue'
import { useCurrentTab } from '@/data/useCurrentTab'

const props = defineProps<{ viewIndex: number }>()

const tab = useCurrentTab()
const collection = computed(() => tab.value?.collectionForView(props.viewIndex) ?? null)
const splitView = computed(() => tab.value?.state.splitView ?? false)
const bound = computed(() => tab.value?.isBound() ?? true)

function toggleBind() {
    tab.value?.toggleBind()
}
</script>

<template>
    <div class="filter-row" v-if="tab && collection">
        <!-- Bind / unbind the two views' filters. Only meaningful when split. -->
        
        <div v-if="splitView" class="bb" :class="{ bound }"
            :title="bound ? 'Views share one filter — click to give each its own' : 'Views filter independently — click to bind them'"
            @click="toggleBind">
            <i :class="bound ? 'bi bi-link-45deg' : 'bi bi-unlock'"></i>
        </div>

        <ImageInstanceDropdown :tab="tab" :collection="collection" />
        <TextSearchInput :tab="tab" :collection="collection" />
        <FilterForm :tab="tab" :collection="collection" />
        <GroupForm :manager="collection.groupManager" />
        <SortForm :manager="collection.sortManager" />
    </div>
</template>

<style scoped>
.filter-row {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--spacing-xs);
    padding: 3px 6px;
}

.bind-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    border: none !important;
    background: none;
    border-radius: var(--radius-sm);
    color: var(--text-tertiary);
    font-size: 15px;
    line-height: 1;
    cursor: pointer;
    transition: background-color var(--transition-fast), color var(--transition-fast);
}

.bind-btn:hover {
    background-color: var(--hover-bg);
    color: var(--text-primary);
}

.bind-btn.bound {
    background-color: var(--primary-light);
    color: var(--primary);
}
</style>
