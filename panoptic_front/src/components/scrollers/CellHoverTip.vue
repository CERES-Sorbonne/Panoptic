<script setup lang="ts">
// The one value tooltip of a scroller's read-only cells (see cellHover.ts). Same look and
// placement as the wTT each row used to carry: above the value, flipped below when there is no
// room, kept inside the window, and closed as soon as its cell is no longer hovered.
import { nextTick, onUnmounted, ref, watch } from 'vue'
import { CellTip } from './cellHover'

const props = defineProps<{
    tip: CellTip | null
}>()

const emits = defineEmits(['hide'])

const popperElem = ref<HTMLElement>(null)
// Measured before it is shown: the first frame lays it out off-screen, transparent.
const placed = ref(false)
const coords = ref({ top: 0, left: -10000 })
let rafId = 0

// Gap between the value and the popup, and the minimum distance kept to the window's edges.
const GAP = 8
const EDGE = 4

function computePosition(anchor: HTMLElement) {
    const r = anchor.getBoundingClientRect()
    const pop = popperElem.value
    const pw = pop ? pop.offsetWidth : 0
    const ph = pop ? pop.offsetHeight : 0
    const vw = window.innerWidth
    const vh = window.innerHeight
    const needed = ph + GAP + EDGE
    const below = r.top < needed && vh - r.bottom >= needed
    let top = below ? r.bottom + GAP : r.top - GAP - ph
    let left = r.left + r.width / 2 - pw / 2
    left = Math.min(Math.max(left, EDGE), Math.max(EDGE, vw - pw - EDGE))
    top = Math.min(Math.max(top, EDGE), Math.max(EDGE, vh - ph - EDGE))
    coords.value = { top, left }
}

// Follows the cell while it scrolls, and closes once the cell is gone (recycled, display:none)
// or the pointer is off it — neither of which always sends a pointerout.
function tick() {
    const anchor = props.tip?.anchor
    if (!anchor || anchor.getClientRects().length === 0 || !anchor.matches(':hover')) {
        stop()
        emits('hide')
        return
    }
    computePosition(anchor)
    placed.value = true
    rafId = requestAnimationFrame(tick)
}

function stop() {
    cancelAnimationFrame(rafId)
    rafId = 0
    placed.value = false
    coords.value = { top: 0, left: -10000 }
}

watch(() => props.tip, async t => {
    stop()
    if (!t) return
    await nextTick()
    rafId = requestAnimationFrame(tick)
})

onUnmounted(stop)
</script>

<template>
    <Teleport to="body">
        <div v-if="props.tip" ref="popperElem" class="cell-tip"
            :style="{ top: coords.top + 'px', left: coords.left + 'px', opacity: placed ? 1 : 0 }">
            <span v-for="line in props.tip.text.split('\n')">{{ line }}<br /></span>
        </div>
    </Teleport>
</template>

<style scoped>
/* wTT's popper (withToolTip.vue), so the shared tooltip reads exactly like the per-row ones did */
.cell-tip {
    position: fixed;
    z-index: 10000;
    width: max-content;
    max-width: min(300px, calc(100vw - 8px));
    max-height: calc(100vh - 8px);
    overflow: auto;
    background: rgba(0, 0, 0, 0.8);
    color: #fff;
    border-radius: 6px;
    padding: 7px 12px 6px;
    font-size: 13px;
    line-height: 1.3;
    word-break: normal;
    word-wrap: break-word;
    pointer-events: none;
}
</style>
