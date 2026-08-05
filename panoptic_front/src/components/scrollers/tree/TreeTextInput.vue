<script setup lang="ts">
// Text / url property row of a tree cell: shows the value, turns into a real editor on click.
// Built for this scroller only — the shared Row*/Cell* inputs size themselves in absolute
// pixels from a width prop, which is exactly what a cell-filling row must not do.
import { computed, nextTick, ref, watch } from 'vue'
import TreeCellFrame from './TreeCellFrame.vue'
import PropertyIcon from '@/components/properties/PropertyIcon.vue'
import { useCellPopup } from './cellPopup'
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

// The editor is a multi-line box: too big for the row, so it lives in a popup parked on the cell.
const { popup, popupElem, place, setWidth, fit, watchViewport, stopWatch } = useCellPopup(frame)

// A cell can be very narrow; wrapping the editor at that width would break the text into a
// column. The popup may therefore grow wider than the cell it covers, up to this.
const MAX_WIDTH = 400
// Air above and below the text, on top of the cell's own insets. Paid for by lifting the popup by
// the same amount, so the first line stays on the pixels it occupied while reading — the knob to
// turn if the editor sits too tight. At 0 the popup is exactly the cell.
const PAD = 0

watch(() => props.modelValue, v => localValue.value = v ?? '')

// A cell row is one line high, so line breaks can't be shown as line breaks: the value is cut
// on them and each break is drawn back as a ⏎ icon, keeping the real text readable on one line.
const lines = computed(() => (props.modelValue ?? '').split(/\r?\n/))

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

// A textarea has no auto height: it must be measured after every change. Collapse first, then
// take scrollHeight, or it can only ever grow. Width first — how tall the text is depends on how
// wide it may run — and only measured once that new width has actually been applied.
async function resize() {
    // +2: the caret sits after the last glyph, and measureText rounds down
    setWidth(textWidth(localValue.value) + 2, MAX_WIDTH)
    await nextTick()
    const elem = inputElem.value as HTMLTextAreaElement
    if (!elem) return
    elem.style.height = 'auto'
    elem.style.height = elem.scrollHeight + 'px'
    fit(elem, popup.value.padTop + popup.value.padBottom + PAD * 2)
}

watch(localValue, resize)

async function focus() {
    editing.value = true
    place()
    popup.value.top -= PAD
    popup.value.icon.top += PAD
    await nextTick()
    inputElem.value?.focus()
    resize()
    watchViewport(close)
}

// Commits and closes, via the textarea's own blur so there is a single close path.
function close() {
    ;(inputElem.value as HTMLElement)?.blur()
    if (editing.value) onBlur()
}

function onClick() {
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
    editing.value = false
    stopWatch()
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
        <div v-if="editing" ref="popupElem" class="cell-popup"
            :style="{ top: popup.top + 'px', left: popup.left + 'px', width: (popup.width + popup.scrollbar) + 'px', paddingTop: (popup.padTop + PAD) + 'px', paddingBottom: (popup.padBottom + PAD) + 'px', maxHeight: popup.maxHeight ? popup.maxHeight + 'px' : undefined }">
            <!-- Same icon, same toggle: it closes the editor it opened. mousedown.prevent so the
                 close is this click's doing rather than the focus loss it would cause first. -->
            <div class="popup-icon" @mousedown.prevent @click="close"
                :style="{ top: popup.icon.top + 'px', left: popup.icon.left + 'px', width: popup.icon.width + 'px', height: popup.icon.height + 'px', fontSize: popup.icon.fontSize }">
                <PropertyIcon :type="props.type" />
            </div>
            <textarea ref="inputElem" class="field" rows="1" v-model="localValue"
                :style="{ ...popup.text, marginLeft: popup.contentLeft + 'px', width: popup.contentWidth + 'px' }"
                @focus="emits('focus')" @blur="onBlur"
                @keydown.enter.ctrl.prevent="e => (e.target as HTMLElement).blur()"
                @keydown.enter.meta.prevent="e => (e.target as HTMLElement).blur()" @keydown.esc.stop="onEscape"
                @keydown.tab.stop.prevent="emits('tab')" />
        </div>
    </Teleport>
</template>

<style scoped>
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
