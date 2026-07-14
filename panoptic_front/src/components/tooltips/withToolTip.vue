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
    if (!el || el.getClientRects().length === 0) {
        hide()
        return
    }
    computePosition()
    rafId = requestAnimationFrame(tick)
}

function show() {
    if (!props.message) return
    clearTimeout(showTimer)
    showTimer = setTimeout(() => {
        computePosition()
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
            :style="{ top: coords.top + 'px', left: coords.left + 'px' }">
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
