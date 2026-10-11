<script setup lang="ts">
/**
 * Virtual scroller for the image views (tree, grid, image wall, cluster cards). See
 * scrollLayout.ts for the layout it reads and virtualView.ts for what it does on a scroll.
 *
 * The owner builds a ScrollLayout over its content and renders a line from its LineRef:
 *
 *   <VirtualScroller ref="vs" :layout="layout" :height="h" @range="onRange" v-slot="{ line, motion }">
 *       <GroupLine v-if="line.index < 0" ... />  <ImageLine v-else ... />
 *   </VirtualScroller>
 *
 * After changing the layout (rebuild, refresh, refreshNode) it calls `relayout()`. The slot
 * content of a line is rendered again only when that slot is given another line, or on
 * `relayout({ rerender: true })`; reactive state the slot content reads re-renders it as usual.
 */
import { onBeforeUnmount, onMounted, provide, shallowReactive, shallowRef, useSlots, watch, ref } from 'vue'
import VsSlot, { slotContextKey } from './vsSlot'
import type { LineRef, NodeId, ScrollLayout } from './scrollLayout'
import { VirtualView } from './virtualView'
import type { Motion, RelayoutAnchor, Slot, ViewHost, ViewRange } from './virtualView'
import { MAX_SCROLL_PX } from '../scrollPager'
import { RowHeights } from '../grid/rowHeights'

const props = withDefaults(defineProps<{
    layout: ScrollLayout
    // Viewport height, px.
    height: number
    // Px mounted beyond the viewport on each side; raised to the tallest line in range.
    overscan?: number
    // Viewports of prefetch range ahead in the scroll direction (range.prefetch; nothing mounted).
    lead?: number
    // Body lines size themselves and are measured (grid rows); otherwise every line gets its size.
    measure?: boolean
    // Tallest DOM height before paging (see scrollPager.ts).
    maxHeight?: number
    // Px/ms above which motion is 'fast'.
    fastSpeed?: number
    // Ms without a scroll event before motion is 'idle' again.
    idleDelay?: number
    // Px of space after the last line, filled by the `tail` slot when given.
    tail?: number
}>(), {
    overscan: 300,
    lead: 1,
    measure: false,
    maxHeight: MAX_SCROLL_PX,
    fastSpeed: 3,
    idleDelay: 120,
    tail: 0,
})

const emit = defineEmits<{
    // One of the ranges starts or ends on another line. Held while motion is 'fast'.
    (e: 'range', range: ViewRange): void
    (e: 'motion', motion: Motion): void
}>()

const slots = useSlots()
const root = ref<HTMLElement | null>(null)
const track = ref<HTMLElement | null>(null)
const tailEl = ref<HTMLElement | null>(null)

const pool = shallowReactive<Slot[]>([])
const motion = shallowRef<Motion>('idle')
const els = new Map<number, HTMLElement>()
// Last transform/height written per slot, so an unchanged position is not written again.
const written = new Map<number, string>()

let measurer: RowHeights<LineRef> | undefined

const host: ViewHost = {
    viewportHeight: () => props.height,
    scrollTop: () => root.value?.scrollTop ?? 0,
    setScrollTop: px => { if (root.value) root.value.scrollTop = px },
    setContentHeight: px => {
        if (track.value) track.value.style.height = px + 'px'
        placeTail()
    },
    createSlot: (id, type) => {
        const slot: Slot = { id, type, line: shallowRef<LineRef | null>(null), key: null, top: 0, size: 0 }
        pool.push(slot)
        return slot
    },
    place: (slot, y, size) => {
        const el = els.get(slot.id)
        if (!el) return
        const state = y === null ? 'none' : y + '|' + (size ?? '')
        if (written.get(slot.id) === state) return
        written.set(slot.id, state)
        if (y === null) {
            el.style.display = 'none'
            return
        }
        el.style.display = ''
        el.style.transform = `translateY(${y}px)`
        el.style.height = size === undefined ? '' : size + 'px'
    },
    lineChanged: slot => {
        const el = els.get(slot.id)
        if (el) measurer?.remeasure(el)
    },
    range: r => emit('range', r),
    motion: m => {
        motion.value = m
        emit('motion', m)
    },
    now: () => performance.now(),
    setTimer: (fn, ms) => setTimeout(fn, ms),
    clearTimer: handle => clearTimeout(handle as ReturnType<typeof setTimeout>),
}

const view = new VirtualView(props.layout, host, {
    overscan: props.overscan,
    lead: props.lead,
    measured: props.measure,
    tail: props.tail,
    fastSpeed: props.fastSpeed,
    idleDelay: props.idleDelay,
}, props.maxHeight)

if (props.measure) {
    measurer = new RowHeights<LineRef>(changes => {
        let changed = false
        for (const [line, px] of changes) changed = view.layout.setMeasured(line, px) || changed
        if (changed) view.relayout()
    }, undefined, line => view.layout.sizeOf(line))
}

provide(slotContextKey, {
    render: (line, slot) => slots.default?.({
        line,
        type: slot.type,
        // A getter: only the slots that read it re-render when it changes.
        get motion() { return motion.value },
    }),
    bind: (slot, el) => {
        const old = els.get(slot.id)
        if (old === el) return
        if (old) measurer?.unobserve(old)
        written.delete(slot.id)
        if (!el) {
            els.delete(slot.id)
            return
        }
        els.set(slot.id, el)
        view.placeSlot(slot)
        // Header slots are observed too (the pool is per type, not per line), but their lines are
        // not reported: only body lines are measured.
        measurer?.observe(el, () => {
            const line = slot.line.value
            return slot.key !== null && line && line.index >= 0 ? line : undefined
        })
    },
})

function placeTail() {
    const el = tailEl.value
    if (!el) return
    el.style.transform = `translateY(${view.tailTop()}px)`
    el.style.height = props.tail + 'px'
}

function onScroll() {
    const offset = view.pager.offset
    view.onScroll()
    if (view.pager.offset !== offset) placeTail()
}

watch(() => props.layout, layout => {
    view.layout = layout
    view.relayout({ rerender: true })
})
watch(() => props.height, () => view.relayout())
watch(() => props.tail, tail => {
    view.options.tail = tail
    view.relayout()
})
watch(() => [props.overscan, props.lead, props.fastSpeed, props.idleDelay] as const, ([overscan, lead, fastSpeed, idleDelay]) => {
    Object.assign(view.options, { overscan, lead, fastSpeed, idleDelay })
})
watch(tailEl, placeTail, { flush: 'post' })

// Hidden (display: none, here or on an ancestor), the element loses its scroll position without a
// scroll event: shown again, it is at the top while the lines are still placed where it was, and
// the viewport is empty. It has no size while hidden, so getting one back is when to put it back
// where the view is (relayout writes the scroll position when the element's differs).
let shown = false
const visibility = new ResizeObserver(entries => {
    const box = entries[entries.length - 1].contentRect
    const now = box.width > 0 && box.height > 0
    if (now && !shown) view.relayout()
    shown = now
})

onMounted(() => {
    root.value?.addEventListener('scroll', onScroll, { passive: true })
    if (root.value) visibility.observe(root.value)
    view.relayout()
})

onBeforeUnmount(() => {
    root.value?.removeEventListener('scroll', onScroll)
    visibility.disconnect()
    view.dispose()
    measurer?.disconnect()
})

defineExpose({
    /** Scrolls to a node's top (its header), or to a line. */
    scrollTo: (target: NodeId | LineRef, align?: 'start' | 'center' | 'nearest') => view.scrollTo(target, align),
    /** Scrolls to a virtual offset. */
    scrollToOffset: (px: number) => view.scrollToOffset(px),
    /** The current virtual scroll position. */
    scrollTop: () => view.virtualTop,
    /** Call after changing the layout. See VirtualView.relayout. */
    relayout: (opts?: { anchor?: RelayoutAnchor, rerender?: boolean }) => view.relayout(opts),
    /** The lines mounted now, in display order. */
    mountedLines: () => view.mountedLines(),
    motion: () => motion.value,
    el: () => root.value,
})
</script>

<template>
    <div ref="root" class="vscroller" :style="{ height: props.height + 'px' }">
        <div ref="track" class="vs-track">
            <VsSlot v-for="slot in pool" :key="slot.id" :state="slot" />
            <div v-if="$slots.tail && props.tail > 0" ref="tailEl" class="vs-tail">
                <slot name="tail" :height="props.tail" />
            </div>
        </div>
    </div>
</template>

<style>
.vscroller {
    position: relative;
    overflow-y: auto;
    /* The scroller keeps what is at the top in place itself (relayout); the browser's own
       anchoring would move it a second time. */
    overflow-anchor: none;
}

.vs-track {
    position: relative;
    width: 100%;
    overflow: hidden;
}

.vs-slot,
.vs-tail {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    will-change: transform;
}

.vs-slot {
    contain: layout style;
}
</style>
