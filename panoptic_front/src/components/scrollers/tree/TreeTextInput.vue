<script setup lang="ts">
// Text / url property row of a tree cell: shows the value, turns into a real input on click.
// Built for this scroller only — the shared Row*/Cell* inputs size themselves in absolute
// pixels from a width prop, which is exactly what a cell-filling row must not do.
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import TreeCellFrame from './TreeCellFrame.vue'
import PropertyIcon from '@/components/properties/PropertyIcon.vue'
import { PropertyType } from '@/data/models'
import { keyState } from '@/data/keyState'

const props = defineProps<{
    modelValue?: string
    // string or url; url values open in a new tab on ctrl/cmd-click instead of editing
    type: PropertyType
}>()

const emits = defineEmits(['update:modelValue', 'focus', 'blur', 'tab'])

const frame = ref(null)
const inputElem = ref(null)
const editing = ref(false)
const localValue = ref(props.modelValue ?? '')
// Fixed-position box of the editor popup, plus the text metrics copied off the cell.
const popup = ref({
    top: 0, left: 0, width: 0,
    // the cell's own width and right padding, the floor and the frame sizeWidth() grows within
    cellWidth: 0, rightPad: 0,
    // both boxes are placed from the cell's own measurements, not re-derived from its CSS
    icon: { top: 0, left: 0, width: 0, height: 0, fontSize: '' },
    textLeft: 0, textWidth: 0,
    text: {} as Record<string, string>,
    // set by fit() when the editor would otherwise run past the bottom of the window
    maxHeight: 0,
    // extra width paid to the vertical scrollbar that the cap brings, so the text keeps the
    // full cell width instead of being pushed under a horizontal scrollbar too
    scrollbar: 0,
})
const popupElem = ref(null)

watch(() => props.modelValue, v => localValue.value = v ?? '')

// A cell row is one line high, so line breaks can't be shown as line breaks: the value is cut
// on them and each break is drawn back as a ⏎ icon, keeping the real text readable on one line.
const lines = computed(() => (props.modelValue ?? '').split(/\r?\n/))

// The editor is a multi-line box inside a virtualized scroller whose cells clip and recycle,
// so it can't live in the cell: it is teleported to the body and parked on the cell's own
// value box, padded outwards by PAD so the text lands exactly where it was reading.
const PAD = 4
// A cell can be very narrow; wrapping the editor at that width would break the text into a
// column. The popup may therefore grow wider than the cell it covers, up to this.
const MAX_WIDTH = 400

function place() {
    const zone = frame.value?.valueZone as HTMLElement
    const cell = frame.value?.root as HTMLElement
    console.log('[TreeTextInput] place', { hasFrame: !!frame.value, hasZone: !!zone, len: (props.modelValue ?? '').length })
    if (!zone || !cell) return
    // Horizontally the popup IS the cell — it carries the property icon too, so it must line its
    // own icon column up with the one it covers. Vertically it hangs off the value's first line.
    const rect = cell.getBoundingClientRect()
    const zoneRect = zone.getBoundingClientRect()
    const iconElem = frame.value?.iconZone as HTMLElement
    const iconRect = iconElem?.getBoundingClientRect()
    const top = zoneRect.top - PAD
    console.log('[TreeTextInput] rect', { cell: rect.top, zone: zoneRect.top, icon: iconRect?.top, height: zoneRect.height })
    const style = getComputedStyle(zone)
    const rightPad = rect.right - zoneRect.right
    popup.value = {
        top,
        left: rect.left,
        // starts as the cell; sizeWidth() grows it only as far as the text actually needs
        width: rect.width,
        cellWidth: rect.width,
        rightPad,
        // The icon and the text keep the exact boxes they occupy in the cell, expressed relative
        // to the popup's own origin — so nothing about the frame's padding is restated here, and
        // opening the editor moves neither of them by a pixel.
        // fontSize included because the icon IS a font glyph, and the popup hangs off the body:
        // it inherits none of the cell's sizing and would otherwise draw at the browser default.
        icon: iconRect
            ? {
                top: iconRect.top - top, left: iconRect.left - rect.left,
                width: iconRect.width, height: iconRect.height,
                fontSize: getComputedStyle(iconElem).fontSize,
            }
            : { top: 0, left: 0, width: 0, height: 0, fontSize: '' },
        textLeft: zoneRect.left - rect.left,
        textWidth: zoneRect.width,
        maxHeight: 0,
        scrollbar: 0,
        // Copied rather than restated: the cell's font depends on which scroller renders it.
        // Property by property, not via the `font` shorthand — that shorthand serializes to ''
        // whenever it can't represent the computed style, which silently drops the textarea back
        // to its own default font and shifts every line off the text it replaced.
        text: {
            fontFamily: style.fontFamily,
            fontSize: style.fontSize,
            fontWeight: style.fontWeight,
            fontStyle: style.fontStyle,
            letterSpacing: style.letterSpacing,
            lineHeight: style.lineHeight,
        },
    }
}

// Natural width of the longest line, measured on a canvas rather than by laying the text out:
// the popup's width has to be known BEFORE the textarea wraps anything, so it can't be read
// back off the textarea itself.
let measureCtx: CanvasRenderingContext2D = null

function textWidth(value: string) {
    const t = popup.value.text
    if (!t.fontSize) return 0
    measureCtx ??= document.createElement('canvas').getContext('2d')
    // canvas shorthand order: style weight size family
    measureCtx.font = `${t.fontStyle} ${t.fontWeight} ${t.fontSize} ${t.fontFamily}`
    return value.split(/\r?\n/).reduce((max, line) => Math.max(max, measureCtx.measureText(line).width), 0)
}

// The cell's width is the default; the popup only grows when the text would otherwise wrap, and
// never past MAX_WIDTH (nor the window).
function sizeWidth() {
    const p = popup.value
    // +2: the caret sits after the last glyph, and measureText rounds down
    const needed = p.textLeft + textWidth(localValue.value) + 2 + p.rightPad
    const ceiling = Math.min(MAX_WIDTH, window.innerWidth - MARGIN * 2)
    p.width = Math.max(p.cellWidth, Math.min(needed, ceiling))
    p.textWidth = p.width - p.textLeft - p.rightPad
}

// A textarea has no auto height: it must be measured after every change. Collapse first, then
// take scrollHeight, or it can only ever grow. Width first — how tall the text is depends on how
// wide it may run — and only measured once that new width has actually been applied.
async function resize() {
    sizeWidth()
    await nextTick()
    const elem = inputElem.value as HTMLTextAreaElement
    if (!elem) return
    elem.style.height = 'auto'
    elem.style.height = elem.scrollHeight + 'px'
    fit()
}

// Fixed to the viewport, the popup would happily grow past its edges — off-screen text, and a
// window the page can't scroll to reach. So once the textarea is measured, keep the whole box
// inside the window: slide it up (and left) to fit, and only when even that isn't enough, cap
// its height and let it scroll inside itself.
const MARGIN = 4

function fit() {
    const elem = popupElem.value as HTMLElement
    if (!elem) return

    const p = popup.value

    // measured off the textarea, not the popup: the popup's own height may still be capped by a
    // previous fit(), whereas the textarea always carries its full content height
    p.maxHeight = 0
    const height = (inputElem.value as HTMLElement).offsetHeight + PAD * 2
    const available = window.innerHeight - MARGIN * 2
    if (height > available) {
        p.maxHeight = available
        p.top = MARGIN
    } else if (p.top + height > window.innerHeight - MARGIN) {
        p.top = window.innerHeight - MARGIN - height
    }

    if (!p.maxHeight) {
        p.scrollbar = 0
        clampLeft()
        return
    }
    // The cap may bring a vertical scrollbar, which on a classic (non-overlay) scrollbar platform
    // eats into the content width and would push the fixed-width textarea under a HORIZONTAL one.
    // Pay for it in width instead — measurable only once the cap is on the element.
    nextTick(() => {
        const capped = popupElem.value as HTMLElement
        if (!capped) return
        p.scrollbar = capped.offsetWidth - capped.clientWidth
        clampLeft()
    })
}

function clampLeft() {
    const p = popup.value
    p.left = Math.max(MARGIN, Math.min(p.left, window.innerWidth - (p.width + p.scrollbar) - MARGIN))
}

watch(localValue, resize)

// Teleported to the body, the popup does not follow the scroller: rather than track it, commit
// and close, which is what clicking away does anyway.
function onScroll(e?: Event) {
    if (!editing.value) return
    // a capped popup scrolls inside itself; that is not the scroller moving out from under it
    const elem = popupElem.value as HTMLElement
    if (e && elem && e.target instanceof Node && elem.contains(e.target)) return
    console.log('[TreeTextInput] closing on scroll/resize')
    ;(inputElem.value as HTMLElement)?.blur()
}

async function focus() {
    editing.value = true
    place()
    await nextTick()
    // Focusing can itself scroll an ancestor (the browser reveals the focused element), so the
    // close-on-scroll listener goes on only once that settled — otherwise the popup closes on
    // the very scroll its own opening caused.
    inputElem.value?.focus()
    resize()
    requestAnimationFrame(() => {
        if (!editing.value) return
        // capture: the scroller scrolls its own element, which doesn't bubble
        window.addEventListener('scroll', onScroll, true)
        window.addEventListener('resize', onScroll)
    })
}

function stopListening() {
    window.removeEventListener('scroll', onScroll, true)
    window.removeEventListener('resize', onScroll)
}

onBeforeUnmount(stopListening)

// Commits and closes, via the textarea's own blur so there is a single close path.
function close() {
    ;(inputElem.value as HTMLElement)?.blur()
    if (editing.value) onBlur()
}

function onClick() {
    console.log('[TreeTextInput] click', { type: props.type, len: (props.modelValue ?? '').length, editing: editing.value })
    // a second click on the row it opened closes it again
    if (editing.value) return close()
    if (props.type == PropertyType.url && props.modelValue && (keyState.ctrl || keyState.cmd)) {
        const url = props.modelValue.startsWith('http') ? props.modelValue : 'http://' + props.modelValue
        window.open(url, '_blank')?.focus()
        return
    }
    focus()
}

function submit() {
    const value = localValue.value === '' ? undefined : localValue.value
    if (value === props.modelValue) return
    emits('update:modelValue', value)
}

function onBlur() {
    console.log('[TreeTextInput] blur')
    editing.value = false
    stopListening()
    submit()
    emits('blur')
}

function onEscape(e: KeyboardEvent) {
    localValue.value = props.modelValue ?? ''
    ;(e.target as HTMLInputElement).blur()
}

defineExpose({ focus })
</script>

<template>
    <!-- the icon stops the cell's click, so it needs the same handler to open the editor too -->
    <TreeCellFrame ref="frame" :type="props.type" :empty="!editing && !props.modelValue" :active="editing"
        @click="onClick" @icon-click="onClick">
        <span v-if="props.modelValue && !editing" class="value" :class="{ url: props.type == PropertyType.url }">
            <template v-for="(line, i) in lines" :key="i"><i v-if="i > 0"
                    class="bi bi-arrow-return-left return-icon" />{{ line }}</template>
        </span>
    </TreeCellFrame>

    <Teleport to="body">
        <!-- Enter inserts a line break (the point of the textarea), so committing moves to
             ctrl/cmd-Enter, alongside the blur and Escape the other rows already use. -->
        <div v-if="editing" ref="popupElem" class="text-popup"
            :style="{ top: popup.top + 'px', left: popup.left + 'px', width: (popup.width + popup.scrollbar) + 'px', paddingTop: PAD + 'px', paddingBottom: PAD + 'px', maxHeight: popup.maxHeight ? popup.maxHeight + 'px' : undefined }">
            <!-- both boxes copied off the cell, so the icon and the first line of text stay
                 exactly where they were reading -->
            <!-- Same icon, same toggle: it closes the editor it opened. mousedown.prevent so the
                 close is this click's doing rather than the focus loss it would cause first. -->
            <div class="popup-icon" @mousedown.prevent @click="close"
                :style="{ top: popup.icon.top + 'px', left: popup.icon.left + 'px', width: popup.icon.width + 'px', height: popup.icon.height + 'px', fontSize: popup.icon.fontSize }">
                <PropertyIcon :type="props.type" />
            </div>
            <textarea ref="inputElem" class="field" rows="1" v-model="localValue"
                :style="{ ...popup.text, marginLeft: popup.textLeft + 'px', width: popup.textWidth + 'px' }" @focus="emits('focus')" @blur="onBlur"
                @keydown.enter.ctrl.prevent="e => (e.target as HTMLElement).blur()"
                @keydown.enter.meta.prevent="e => (e.target as HTMLElement).blur()" @keydown.esc.stop="onEscape"
                @keydown.tab.stop.prevent="emits('tab')" />
        </div>
    </Teleport>
</template>

<style scoped>
/* Parked on the cell it edits, above the scroller and any card clipping. Its own surface and
   ring, since it is no longer inside the frame that used to draw them. */
.text-popup {
    position: fixed;
    z-index: 2000;
    box-sizing: border-box;
    background: white;
    /* The ring is an outline, not an inset shadow: an inset shadow on a scrolling box is painted
       against the scrolled content, so it drops off the right and bottom edges as soon as the
       cap brings a scrollbar. An outline is painted on the border box and costs no layout. */
    outline: 1px solid var(--blue);
    outline-offset: -1px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
    border-radius: 3px;
    /* only ever reached once fit() caps the height: a value taller than the window scrolls
       here, inside the popup, rather than running off the screen */
    overflow-y: auto;
}

/* Parked on the box the cell's own icon occupies (see place()), so it never drifts with the
   text growing below it. */
.popup-icon {
    position: absolute;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--grey-text);
}

/* The popup already is the box: the textarea itself brings none — same font and metrics as
   the value it replaces, no border, no padding, so nothing moves when it appears. */
.field {
    display: block;
    box-sizing: border-box;
    appearance: none;
    -webkit-appearance: none;
    padding: 0;
    margin: 0;
    border: none;
    outline: none;
    background: transparent;
    color: inherit;
    /* height is driven by resize(); the manual grip and the scrollbar would both fight it */
    resize: none;
    overflow: hidden;
}

.value {
    display: block;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
}

/* Reads as punctuation between the two lines it joins, not as a word: smaller, greyed, and
   given its own breathing space so the text either side stays legible. */
.return-icon {
    color: var(--grey-text);
    font-size: 0.85em;
    margin: 0 3px;
    vertical-align: baseline;
}

.url {
    color: var(--blue);
}
</style>
