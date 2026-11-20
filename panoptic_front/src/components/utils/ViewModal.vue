<script setup lang="ts">
// A panel centered over part of the view area (see data/composables/viewModal.ts).
// Fixed-positioned over the target element's rect, tracked live so it follows
// split drags and window resizes. Closes on backdrop click and Escape.
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useCurrentTab } from '@/data/composables/useCurrentTab'
import { useModalStore } from '@/data/stores/modalStore'
import { resolveViewModalTarget, ViewModalScope } from '@/data/composables/viewModal'

const props = withDefaults(defineProps<{
    show: boolean
    scope: ViewModalScope
    width?: number
    // No header row (title + close): the content is the whole panel (e.g. a Spotlight-like search).
    bare?: boolean
    // 'top' puts the panel in the upper part of the target instead of its center.
    placement?: 'center' | 'top'
}>(), {
    width: 420,
    bare: false,
    placement: 'center'
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

// 'top': the panel starts at ~18% of the target height (16px..140px), like Spotlight.
const backdropStyle = computed(() => {
    const r = rect.value
    const style: Record<string, string> = {
        top: r.top + 'px', left: r.left + 'px', width: r.width + 'px', height: r.height + 'px'
    }
    if (props.placement === 'top') {
        style.paddingTop = Math.round(Math.max(16, Math.min(140, r.height * 0.18))) + 'px'
    }
    return style
})
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
    // First field, else an element the content marks (e.g. a form's primary button).
    const el = panelElem.value?.querySelector<HTMLElement>('input, textarea, [contenteditable="true"], [data-autofocus]')
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

// The split state can change while open: re-target.
watch(() => [
    props.show && tab.value?.state.splitView,
    props.show && tab.value?.isBound()
], () => { if (props.show) nextTick(attach) })

onBeforeUnmount(() => { detach(); setCounted(false) })
</script>

<template>
    <Teleport to="body">
        <div v-if="show" class="vm-backdrop" :class="{ 'vm-top': props.placement === 'top' }"
            :style="backdropStyle" @mousedown.self="close">
            <div ref="panelElem" class="vm-panel" :class="{ 'vm-bare': props.bare }" tabindex="-1"
                :style="{ width: props.width + 'px' }"
                @keydown.escape.stop="close">
                <div v-if="!props.bare" class="vm-header">
                    <div class="vm-title"><slot name="title"></slot></div>
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
    border-radius: var(--island-radius, 10px);
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

.vm-top {
    align-items: flex-start;
}

/* Headerless variant: larger rounding, softer and deeper shadow. Not clipped, so the
   non-teleported popups of its content (e.g. plugin options) can overflow it. */
.vm-panel.vm-bare {
    border: 1px solid rgba(0, 0, 0, 0.08);
    border-radius: 12px;
    box-shadow: 0 24px 60px rgba(0, 0, 0, 0.28), 0 4px 14px rgba(0, 0, 0, 0.1);
    overflow: visible;
}

/* Flex column so content can shrink to the panel's max-height and scroll a part of
   itself (e.g. ActionForm's params between its fixed header and footer). */
.vm-bare > .vm-body {
    display: flex;
    flex-direction: column;
    overflow: visible;
    border-radius: inherit;
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
