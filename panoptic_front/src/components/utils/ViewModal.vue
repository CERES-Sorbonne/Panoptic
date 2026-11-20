<script setup lang="ts">
// A panel centered over part of the view area (see data/composables/viewModal.ts).
// Fixed-positioned over the target element's rect, tracked live so it follows
// split drags and window resizes. Closes on backdrop click and Escape.
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useCurrentTab } from '@/data/composables/useCurrentTab'
import { useModalStore } from '@/data/stores/modalStore'
import { resolveViewModalTarget, viewModalCoverFilters, ViewModalScope } from '@/data/composables/viewModal'

const props = withDefaults(defineProps<{
    show: boolean
    scope: ViewModalScope
    width?: number
}>(), {
    width: 420
})
const emits = defineEmits(['update:show', 'close'])

const tab = useCurrentTab()
const modalStore = useModalStore()
let counted = false

function setCounted(v: boolean) {
    if (v === counted) return
    counted = v
    modalStore.viewModalsOpen += v ? 1 : -1
}
const rect = ref({ top: 0, left: 0, width: 0, height: 0 })
const panelElem = ref<HTMLElement>()

let target: HTMLElement | null = null
let observer: ResizeObserver | null = null

function measure() {
    if (!target) return
    const r = target.getBoundingClientRect()
    rect.value = { top: r.top, left: r.left, width: r.width, height: r.height }
}

function attach() {
    detach()
    target = resolveViewModalTarget(props.scope, tab.value)
    if (!target) return
    measure()
    observer = new ResizeObserver(measure)
    observer.observe(target)
    window.addEventListener('resize', measure)
}

function detach() {
    observer?.disconnect()
    observer = null
    target = null
    window.removeEventListener('resize', measure)
}

function close() {
    emits('update:show', false)
    emits('close')
}

async function focusFirst() {
    await nextTick()
    const el = panelElem.value?.querySelector<HTMLElement>('input, textarea, [contenteditable="true"]')
    ;(el ?? panelElem.value)?.focus()
}

watch(() => props.show, (show) => {
    if (show) {
        attach()
        setCounted(true)
        focusFirst()
    } else {
        detach()
        setCounted(false)
    }
}, { immediate: true })

// The split state or the coverage setting can change while open: re-target.
watch(() => [
    props.show && tab.value?.state.splitView,
    props.show && tab.value?.isBound(),
    viewModalCoverFilters.value
], () => { if (props.show) nextTick(attach) })

onBeforeUnmount(() => { detach(); setCounted(false) })
</script>

<template>
    <Teleport to="body">
        <div v-if="show" class="vm-backdrop"
            :style="{ top: rect.top + 'px', left: rect.left + 'px', width: rect.width + 'px', height: rect.height + 'px' }"
            @mousedown.self="close">
            <div ref="panelElem" class="vm-panel" tabindex="-1"
                :style="{ width: props.width + 'px' }"
                @keydown.escape.stop="close">
                <div class="vm-header">
                    <div class="vm-title"><slot name="title"></slot></div>
                    <div class="sb vm-icon" :title="viewModalCoverFilters ? 'Cover views only' : 'Cover filter bar too'"
                        @click="viewModalCoverFilters = !viewModalCoverFilters">
                        <i :class="viewModalCoverFilters ? 'bi bi-arrows-angle-contract' : 'bi bi-arrows-angle-expand'" />
                    </div>
                    <div class="sb vm-icon" @click="close"><i class="bi bi-x-lg" /></div>
                </div>
                <div class="vm-body">
                    <slot :close="close"></slot>
                </div>
            </div>
        </div>
    </Teleport>
</template>

<style scoped>
/* Below the #popup dropdown layer (9990) so selects opened inside still show on top,
   and below the global modals (9000+). */
.vm-backdrop {
    position: fixed;
    z-index: 8000;
    display: flex;
    align-items: center;
    justify-content: center;
    background-color: rgba(0, 0, 0, 0.4);
    border-radius: var(--radius-md, 8px);
    padding: 16px;
    box-sizing: border-box;
}

.vm-panel {
    max-width: 100%;
    max-height: 100%;
    display: flex;
    flex-direction: column;
    background: white;
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md, 8px);
    box-shadow: 0 8px 28px rgba(0, 0, 0, 0.18);
    outline: none;
    overflow: hidden;
}

.vm-header {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 4px 6px 4px 10px;
    border-bottom: 1px solid var(--border-color);
    font-size: 14px;
}

.vm-title {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.vm-icon {
    font-size: 12px;
    padding: 2px 5px;
    cursor: pointer;
}

.vm-body {
    min-height: 0;
    overflow: auto;
}
</style>
