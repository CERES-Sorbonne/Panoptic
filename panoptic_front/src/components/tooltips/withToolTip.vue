<script lang="ts">
// Module scope (shared by every instance): only one tooltip may be on screen at a time, so a
// trigger that opens one closes whichever other instance is still showing. Without this, any
// instance that missed its mouseleave keeps its popup up while the next one opens.
const active: { close: (() => void) | null } = { close: null }
</script>

<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue';
import { useI18n } from 'vue-i18n'

// This component has two root nodes (the trigger + the teleported popup), so
// Vue can't auto-inherit attributes like `class`. Bind them to the trigger
// span explicitly instead.
defineOptions({ inheritAttrs: false })

const { t } = useI18n({ useScope: 'global' })

const props = defineProps({
    pos: {
        type: String,
        default: "top"
    },
    message: String,
    icon: {
        type: Boolean,
        default: false
    },
    iconPos: {
        type: String,
        default: "right"
    },
    click: {
        type: Boolean,
        default: true
    },
    // Delay before the tooltip appears on hover (ms).
    delay: {
        type: Number,
        default: 200
    }
})

const realMessage = computed(() => {
    if (!props.message) return
    let res = ''
    if (['main', 'modals', 'dropdown', 'btn'].indexOf(props.message.split('.')[0]) > -1) {
        res = t(props.message)
    } else if (props.message.startsWith('.')) {
        res = t(props.message.slice(1))
    }
    else {
        res = props.message
    }
    const resList = res.split('\n')
    return resList
})

// Self-contained tooltip (no floating-vue). The popup is teleported to <body>
// so it isn't clipped by ancestors with overflow:hidden, and its visibility is
// driven entirely by our own reactive `visible` flag — so we can always close
// it deterministically.
//
// The tricky case this solves: a v-show="false" on an ancestor hides the
// trigger via display:none WITHOUT firing mouseleave (e.g. the hover-revealed
// fast actions in GroupLine.vue). While the tooltip is open we run a small rAF
// loop that both repositions the popup (so it follows scrolling) and checks
// whether the trigger is still actually rendered. getClientRects() is empty
// whenever the element or any ancestor is display:none, which lets us detect
// that case and close. The loop only runs while a tooltip is visible.
const triggerElem = ref<HTMLElement | null>(null)
const popperElem = ref<HTMLElement | null>(null)
const visible = ref(false)
// The popup can only be positioned once it exists in the DOM (it has to be measured), so the
// first computePosition() runs with a 0x0 size and lands in the wrong place. Stay transparent
// until the first tick has measured and repositioned it, so no misplaced frame is ever painted.
const placed = ref(false)
const coords = ref({ top: 0, left: 0 })
let showTimer: ReturnType<typeof setTimeout> | undefined
let rafId = 0

// Gap between the trigger and the popup, and the minimum distance kept between
// the popup and the viewport edges.
const GAP = 8
const EDGE = 4
const OPPOSITE: Record<string, string> = { top: 'bottom', bottom: 'top', left: 'right', right: 'left' }

// The popup is measured, not just anchored: we flip to the opposite side when
// the requested one doesn't have room, then clamp the final rect inside the
// viewport so the tooltip is always fully visible.
function computePosition() {
    const el = triggerElem.value
    const pop = popperElem.value
    if (!el) return
    const r = el.getBoundingClientRect()
    const pw = pop ? pop.offsetWidth : 0
    const ph = pop ? pop.offsetHeight : 0
    const vw = window.innerWidth
    const vh = window.innerHeight

    let pos: string = props.pos
    if (pop) {
        const space: Record<string, number> = { top: r.top, bottom: vh - r.bottom, left: r.left, right: vw - r.right }
        const size: Record<string, number> = { top: ph, bottom: ph, left: pw, right: pw }
        const needed = (size[pos] ?? ph) + GAP + EDGE
        const flipped = OPPOSITE[pos] ?? 'bottom'
        if (space[pos] < needed && space[flipped] >= needed) pos = flipped
    }

    let top: number
    let left: number
    switch (pos) {
        case 'bottom': top = r.bottom + GAP; left = r.left + r.width / 2 - pw / 2; break
        case 'left': left = r.left - GAP - pw; top = r.top + r.height / 2 - ph / 2; break
        case 'right': left = r.right + GAP; top = r.top + r.height / 2 - ph / 2; break
        case 'top':
        default: top = r.top - GAP - ph; left = r.left + r.width / 2 - pw / 2; break
    }

    left = Math.min(Math.max(left, EDGE), Math.max(EDGE, vw - pw - EDGE))
    top = Math.min(Math.max(top, EDGE), Math.max(EDGE, vh - ph - EDGE))
    coords.value = { top, left }
}

function tick() {
    const el = triggerElem.value
    // Trigger (or an ancestor) became display:none without a mouseleave — close.
    // Same for a trigger the pointer is no longer over: hover-revealed buttons can be
    // re-rendered or moved out from under the cursor without ever firing mouseleave,
    // which is what leaves a tooltip stranded on screen.
    if (!el || el.getClientRects().length === 0 || !el.matches(':hover')) {
        hide()
        return
    }
    computePosition()
    placed.value = true
    rafId = requestAnimationFrame(tick)
}

function show() {
    if (!props.message) return
    clearTimeout(showTimer)
    showTimer = setTimeout(() => {
        if (active.close && active.close !== hide) active.close()
        active.close = hide
        placed.value = false
        // Park it out of the way for the measuring frame instead of at stale/unmeasured
        // coordinates, so it is laid out with the full max-width available to it.
        coords.value = { top: 0, left: -10000 }
        visible.value = true
        cancelAnimationFrame(rafId)
        rafId = requestAnimationFrame(tick)
    }, props.delay)
}

function hide() {
    clearTimeout(showTimer)
    cancelAnimationFrame(rafId)
    rafId = 0
    visible.value = false
    placed.value = false
    if (active.close === hide) active.close = null
}

onUnmounted(hide)
</script>

<template>
    <span ref="triggerElem" v-bind="$attrs" class="wtt-trigger text-nowrap m-0 p-0" @mouseenter="show" @mouseleave="hide">
        <span v-if="props.icon && props.iconPos === 'left'" style="cursor: pointer;" class="flex-center">
            <i class="bi bi-question-circle small-icon"></i>
        </span>
        <slot></slot>
        <span v-if="props.icon && props.iconPos === 'right'" style="cursor: pointer;"> <i
                class="bi bi-question-circle small-icon"></i></span>
    </span>
    <Teleport to="body">
        <div v-if="visible && realMessage" ref="popperElem" class="wtt-popper"
            :style="{ top: coords.top + 'px', left: coords.left + 'px', opacity: placed ? 1 : 0 }">
            <span v-for="line in realMessage">{{ line }}<br /></span>
        </div>
    </Teleport>
</template>

<style scoped="true">
.wtt-trigger {
    display: inline-flex;
    align-items: center;
}

.small-icon {
    font-size: 9px;
    margin-left: 5px;
    margin-right: 5px;
}

.wtt-popper {
    position: fixed;
    z-index: 10000;
    /* Size the box from its text alone, never from where it happens to sit: a shrink-to-fit
       fixed box is also bounded by (viewport edge - left), so a popup laid out near an edge
       would wrap differently than once it is moved to its final spot — the text visibly
       reflowing from 3 lines to 2. `max-content` + `max-width` makes wrapping depend only on
       the max-width, so the shape measured on the first frame is the final shape. */
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
