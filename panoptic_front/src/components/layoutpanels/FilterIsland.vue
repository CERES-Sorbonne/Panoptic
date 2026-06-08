<script setup lang="ts">
import { computed } from 'vue'
import IslandPanel from '@/layouts/IslandPanel.vue'
import FilterPanel from '@/components/layoutpanels/FilterPanel.vue'
import { useCurrentTab } from '@/data/useCurrentTab'

const tab = useCurrentTab()
const splitView = computed(() => tab.value?.state.splitView ?? false)
const bound = computed(() => tab.value?.isBound() ?? true)
const splitRatio = computed(() => tab.value?.state.splitRatio ?? 0.5)
</script>

<template>
    <template v-if="tab">
        <div v-if="splitView && !bound" class="filter-split">
            <IslandPanel class="filter-primary">
                <FilterPanel :view-index="0" />
            </IslandPanel>
            <IslandPanel :style="{ width: splitRatio * 100 + '%' }" class="filter-secondary">
                <FilterPanel :view-index="1" />
            </IslandPanel>
        </div>
        <IslandPanel v-else>
            <FilterPanel :view-index="0" />
        </IslandPanel>
    </template>
</template>

<style scoped>
.filter-split {
    display: flex;
    flex-direction: row;
    flex-shrink: 0;
    width: 100%;
    gap: 10px;
}

.filter-primary {
    flex: 1;
    min-width: 0;
}

.filter-secondary {
    flex-shrink: 0;
    min-width: 0;
}
</style>
