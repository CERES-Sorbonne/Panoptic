<script setup lang="ts">
// One labeled, collapsible panel inside the reco workspace. Wraps a virtualized
// ImageScroller sized to its own body via a ResizeObserver (same pattern as
// ViewPanel). Fed a plain instance list (queue / group / blacklist) and its own
// selection namespace. When collapsed only the header remains.
import { computed, onMounted, onUnmounted, ref } from 'vue'
import IslandPanel from '@/layouts/IslandPanel.vue'
import ImageScroller from '@/components/scrollers/image/ImageScroller.vue'
import { Instance } from '@/data/models'
import { useColumnStore } from '@/data/columnStore'
import wTT from '@/components/tooltips/withToolTip.vue'
import SelectCircle from '@/components/inputs/SelectCircle.vue'

const props = defineProps<{
    title: string
    instances: Instance[]
    imageSize: number
    inputKey: string
    // ColumnStore selection namespace, private to this panel.
    selectNamespace: string
    collapsed?: boolean
    emptyMessage?: string
}>()

const emit = defineEmits(['toggle'])

const col = useColumnStore()
const ns = computed(() => props.selectNamespace)
const count = computed(() => props.instances.length)
const selectedCount = computed(() => {
    col.selectionTick(ns.value) // reactive dep on this namespace's selection
    return col.selectedCount(ns.value)
})

// All panel images selected (drives the header select-all circle).
const allSelected = computed(() => count.value > 0 && selectedCount.value >= count.value)

function toggleAll() {
    const ids = props.instances.map(i => i.id)
    if (allSelected.value) col.deselectIds(ids, ns.value)
    else col.selectIds(ids, ns.value)
}

function clearSelection() {
    col.clearSelection(ns.value)
}

const bodyRef = ref<HTMLElement>()
const dims = ref({ width: 0, height: 0 })

let observer: ResizeObserver | null = null

onMounted(() => {
    if (bodyRef.value) {
        observer = new ResizeObserver(entries => {
            for (const entry of entries) {
                const { width, height } = entry.contentRect
                dims.value = { width, height }
            }
        })
        observer.observe(bodyRef.value)
    }
})

onUnmounted(() => {
    if (observer && bodyRef.value) observer.unobserve(bodyRef.value)
})
</script>

<template>
    <IslandPanel :grow="!collapsed">
        <template #header>
            <div class="tw-header" @click="emit('toggle')">
                <button class="collapse-btn" @click.stop="emit('toggle')">
                    <i :class="collapsed ? 'bi bi-chevron-right' : 'bi bi-chevron-down'"></i>
                </button>
                <span v-if="count > 0" class="tw-select" @click.stop>
                    <SelectCircle :small="true" :model-value="allSelected" @update:model-value="toggleAll" />
                </span>
                <span class="tw-title">{{ title }}</span>
                <span class="tw-count">{{ count }}</span>

                <!-- Per-panel selection: count, actions, clear (independent namespace) -->
                <template v-if="selectedCount > 0">
                    <div class="sel-sep"></div>
                    <span class="sel-count">{{ $t('main.reco.selected', { count: selectedCount }) }}</span>
                    <div class="sel-actions" @click.stop>
                        <slot name="actions" :count="selectedCount" />
                    </div>
                    <wTT message="main.reco.clear">
                        <button class="sel-clear" @click.stop="clearSelection">
                            <i class="bi bi-x-circle"></i>
                        </button>
                    </wTT>
                </template>
            </div>
        </template>
        <!-- v-show (not v-if) keeps the observed element mounted across collapse. -->
        <div v-show="!collapsed" ref="bodyRef" class="panel-body">
            <ImageScroller
                v-if="dims.width > 0 && dims.height > 0 && count > 0"
                :input-key="inputKey"
                :instances="instances"
                :image-size="imageSize"
                :height="dims.height"
                :width="dims.width"
                :properties="[]"
                :select-namespace="selectNamespace"
                :no-drag="true"
                :hide-if-modal="true"
            />
            <div v-else-if="count === 0" class="panel-empty text-secondary">
                {{ emptyMessage ?? '—' }}
            </div>
        </div>
    </IslandPanel>
</template>

<style scoped>
.tw-header {
    display: flex;
    align-items: center;
    gap: var(--spacing-xs);
    height: 26px;
    padding: 0 var(--spacing-xs);
    background-color: var(--bg-secondary);
    cursor: pointer;
    user-select: none;
}

.collapse-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    border: none;
    background: none;
    padding: 0;
    color: var(--text-secondary);
    cursor: pointer;
    font-size: 11px;
}

.tw-select {
    display: inline-flex;
    align-items: center;
}

.tw-title {
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-semibold);
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.02em;
}

.tw-count {
    font-size: var(--font-size-xs);
    color: var(--text-tertiary);
}

.sel-sep {
    width: 1px;
    height: 14px;
    background-color: var(--border-color);
    margin: 0 var(--spacing-xs);
}

.sel-count {
    font-size: var(--font-size-xs);
    color: var(--text-primary);
    font-weight: var(--font-weight-medium);
    white-space: nowrap;
}

.sel-actions {
    display: inline-flex;
    align-items: center;
    gap: var(--spacing-xs);
}

.sel-clear {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border: none;
    background: none;
    padding: 0 2px;
    color: var(--text-secondary);
    cursor: pointer;
    font-size: 13px;
}

.sel-clear:hover {
    color: var(--text-primary);
}

.panel-body {
    position: relative;
    flex: 1;
    min-height: 0;
    overflow: hidden;
    padding: var(--spacing-xs);
}

.panel-empty {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    font-size: 13px;
}
</style>
