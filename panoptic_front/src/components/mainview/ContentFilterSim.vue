<script setup lang="ts">
import { ref } from 'vue'

// Simulated filtering zone for the base layout — a presentational stand-in for
// ContentFilter.vue (search / view-mode / size / filter-group-sort) with no
// store or TabManager dependencies.
const searchText = ref('')
const viewMode = ref('grid')
const imageMode = ref<'image' | 'images'>('image')
const imageSize = ref(135)

const viewModes = [
    { id: 'grid', icon: 'bi-grid-3x3-gap-fill', title: 'Grid' },
    { id: 'table', icon: 'bi-table', title: 'Table' },
    { id: 'graph', icon: 'bi-bar-chart', title: 'Graph' },
    { id: 'map', icon: 'bi-map', title: 'Map' },
]
</script>

<template>
    <div class="content-filter">
        <!-- Row 1: search, view modes, image size, instance/image mode -->
        <div class="filter-row">
            <div class="search-box">
                <i class="bi bi-search search-icon"></i>
                <input v-model="searchText" class="search-field" type="text" placeholder="Search images…" />
            </div>

            <div class="tool-group">
                <button
                    v-for="m in viewModes"
                    :key="m.id"
                    class="tool"
                    :class="{ selected: viewMode === m.id }"
                    :title="m.title"
                    @click="viewMode = m.id"
                >
                    <i class="bi" :class="m.icon"></i>
                </button>
            </div>

            <div class="size-control" title="Image size">
                <i class="bi bi-aspect-ratio"></i>
                <input v-model.number="imageSize" class="size-range" type="range" min="30" max="500" />
            </div>

            <div class="tool-group">
                <button class="tool" :class="{ selected: imageMode === 'image' }" title="Instance mode" @click="imageMode = 'image'">
                    <i class="bi bi-image"></i>
                </button>
                <button class="tool" :class="{ selected: imageMode === 'images' }" title="Image mode" @click="imageMode = 'images'">
                    <i class="bi bi-images"></i>
                </button>
            </div>

            <div class="spacer"></div>
            <a class="issue-link" href="https://github.com/CERES-Sorbonne/Panoptic/issues/new/choose" target="_blank" title="Report an issue">
                <i class="bi bi-cone-striped"></i>
            </a>
        </div>

        <!-- Row 2: filter / group / sort -->
        <div class="filter-row sub-row">
            <button class="chip-btn"><i class="bi bi-funnel"></i><span>Filter</span></button>
            <button class="chip-btn"><i class="bi bi-collection"></i><span>Group</span></button>
            <button class="chip-btn"><i class="bi bi-sort-down"></i><span>Sort</span></button>
            <div class="spacer"></div>
            <span class="result-count">1 240 images</span>
        </div>
    </div>
</template>

<style scoped>
.content-filter {
    display: flex;
    flex-direction: column;
    flex-shrink: 0;
    background-color: var(--bg-primary);
}

.filter-row {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
    padding: var(--spacing-xs) var(--spacing-sm);
}

.sub-row {
    padding-top: 0;
}

.search-box {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-shrink: 0;
    width: 200px;
    padding: 3px var(--spacing-sm);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    background-color: var(--bg-primary);
}

.search-box:focus-within {
    border-color: var(--primary);
}

.search-icon {
    color: var(--text-tertiary);
    font-size: 12px;
}

.search-field {
    flex: 1;
    min-width: 0;
    border: none;
    outline: none;
    background: none;
    font-size: var(--font-size-sm);
    color: var(--text-primary);
}

.tool-group {
    display: flex;
    align-items: center;
    gap: 2px;
}

.tool {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 26px;
    height: 26px;
    background: none;
    border: none;
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    transition: background-color var(--transition-fast);
}

.tool:hover {
    background-color: var(--hover-bg);
    color: var(--text-primary);
}

.tool.selected {
    background-color: var(--primary-light);
    color: var(--primary);
}

.size-control {
    display: flex;
    align-items: center;
    gap: 6px;
    color: var(--text-secondary);
}

.size-range {
    width: 90px;
    accent-color: var(--primary);
}

.spacer {
    flex: 1;
}

.issue-link {
    color: var(--text-tertiary);
}

.issue-link:hover {
    color: var(--text-secondary);
}

.chip-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    height: 26px;
    padding: 0 10px;
    background-color: var(--bg-secondary);
    border: 1px solid var(--border-light);
    border-radius: var(--radius-md);
    color: var(--text-primary);
    font-size: var(--font-size-sm);
    transition: background-color var(--transition-fast);
}

.chip-btn:hover {
    background-color: var(--hover-bg);
}

.result-count {
    font-size: var(--font-size-xs);
    color: var(--text-tertiary);
}
</style>
