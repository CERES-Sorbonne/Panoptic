<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';
import Dropdown from '@/components/dropdowns/Dropdown.vue';
import TextInput from './TextInput.vue';

const props = withDefaults(defineProps<{
    modelValue?: string
    icon?: string
    // Caps how wide the expanded popup may grow (it otherwise widens with the text).
    maxWidth?: number
    // Caps how tall the expanded popup may grow; past it the text scrolls.
    maxHeight?: number
    teleport?: boolean
    placeholder?: string
}>(), {
    icon: 'bi-pencil',
    maxWidth: 400,
    maxHeight: 200
})

const emits = defineEmits(['update:modelValue', 'focus', 'blur', 'tab'])

defineExpose({ focus, open, close })

const rootElem = ref(null)
const dropdownElem = ref(null)
const inlineInput = ref(null)

const popupBox = ref(null)

const localValue = ref(undefined)
const isFocus = ref(false)
const isOpen = ref(false)
const aligned = ref(false)
const shift = ref({ x: 0, y: 0 })
// Height of the collapsed box: the popup is pulled up by exactly this much so it
// lands on top of it and the icon does not move when expanding.
const boxHeight = ref(0)
const popupWidth = ref(0)

const offset = computed(() => -boxHeight.value)

function loadValue() {
    localValue.value = props.modelValue
}

function measureBox() {
    if (rootElem.value) {
        boxHeight.value = rootElem.value.offsetHeight
    }
}

function computeWidth() {
    const canvas = document.createElement('canvas')
    const ctx = canvas.getContext('2d')
    ctx.font = '14px Arial'
    const length = ctx.measureText(localValue.value ?? '').width

    let goal = 200
    if (length > 500) goal = 200
    if (length > 800) goal = 300
    if (length > 1000) goal = 400

    const boxWidth = rootElem.value ? rootElem.value.offsetWidth : 0
    // never shrink below the collapsed box, otherwise the overlay would visibly reflow
    goal = Math.max(goal, boxWidth)
    popupWidth.value = Math.min(goal, props.maxWidth)
}

function submit() {
    let value = localValue.value
    if (value == '') value = undefined
    emits('update:modelValue', value)
}

function cancel() {
    loadValue()
}

function focus() {
    if (inlineInput.value) inlineInput.value.focus()
}

function open() {
    if (dropdownElem.value) dropdownElem.value.show()
}

function close() {
    if (dropdownElem.value) dropdownElem.value.hide()
}

function toggle() {
    if (isOpen.value) close()
    else open()
}

// The popper is positioned on whole device pixels, while the collapsed box can sit at a
// fractional x/y (column widths are computed). That mismatch is what makes the text jump by
// a pixel when opening. Rather than trying to predict the rounding, the popup is measured
// against the collapsed box once the popper has been placed, and the leftover delta is
// applied as a transform. Until that happened the popup stays hidden and the collapsed box
// stays visible, so neither a misplaced popup nor an empty slot is ever painted.
// Measured against the *untransformed* popup: the current shift is subtracted back out, so
// align() converges in one pass and can be re-run at will.
function align() {
    if (!rootElem.value || !popupBox.value) return
    const from = rootElem.value.getBoundingClientRect()
    const to = popupBox.value.getBoundingClientRect()
    shift.value = {
        x: shift.value.x + (from.left - to.left),
        y: shift.value.y + (from.top - to.top)
    }
}

// The popup grows as the text wraps. Every growth makes floating-vue re-place it (and, once
// it no longer fits below, flip or shift it), which moves the box away from the collapsed
// one it is supposed to be sitting on. Re-pinning on every resize keeps its top-left welded
// to the collapsed box no matter what the positioning engine decides.
let resizeObserver: ResizeObserver | null = null

function observePopup() {
    stopObserving()
    if (!popupBox.value) return
    resizeObserver = new ResizeObserver(() => align())
    resizeObserver.observe(popupBox.value)
}

function stopObserving() {
    if (resizeObserver) {
        resizeObserver.disconnect()
        resizeObserver = null
    }
}

function onShow() {
    isOpen.value = true
    aligned.value = false
    shift.value = { x: 0, y: 0 }
    measureBox()
    computeWidth()
    requestAnimationFrame(() => {
        if (!isOpen.value) return
        align()
        aligned.value = true
        observePopup()
    })
    emits('focus')
}

function onHide() {
    isOpen.value = false
    aligned.value = false
    stopObserving()
    submit()
    emits('blur')
}

onMounted(async () => {
    loadValue()
    await nextTick()
    measureBox()
})
onUnmounted(stopObserving)
watch(() => props.modelValue, loadValue)
</script>

<template>
    <Dropdown ref="dropdownElem" :offset="offset" :skidding="0" :no-shadow="true" :teleport="props.teleport"
        :auto-focus="false" placement="bottom-start" @show="onShow" @hide="onHide">
        <template #button>
            <!-- collapsed: fills all the horizontal space it is given -->
            <div ref="rootElem" class="icon-input"
                :class="{ 'highlight': isFocus, 'invisible-content': isOpen && aligned }">
                <div class="icon-zone" @click.stop="toggle">
                    <slot name="icon">
                        <i class="bi" :class="props.icon" />
                    </slot>
                </div>
                <div class="field-zone single-line" @click.stop>
                    <TextInput ref="inlineInput" v-model="localValue" :no-shadow="true" :min-height="22" :no-nl="true"
                        :blur-on-enter="true" @submit="submit" @cancel="cancel" @focus="isFocus = true; emits('focus')"
                        @blur="isFocus = false; submit(); emits('blur')" @tab="emits('tab')" />
                </div>
            </div>
        </template>
        <template #popup="{ hide }">
            <!-- expanded: same box geometry, grows with the text.
                 Kept at opacity 0 (not visibility:hidden, which would prevent the
                 contenteditable from auto-focusing) until align() has run. -->
            <div ref="popupBox" class="icon-input icon-input-popup highlight" :style="{
                width: popupWidth + 'px',
                transform: `translate(${shift.x}px, ${shift.y}px)`,
                opacity: aligned ? 1 : 0
            }">
                <div class="icon-zone" @click.stop="hide()">
                    <slot name="icon">
                        <i class="bi" :class="props.icon" />
                    </slot>
                </div>
                <div class="field-zone scroll-zone" :style="{ maxHeight: props.maxHeight + 'px' }" @click.stop>
                    <TextInput v-model="localValue" :auto-focus="true" :no-shadow="true" :min-height="22"
                        :blur-on-enter="true" @submit="hide()" @cancel="cancel(); hide()" @tab="emits('tab')" />
                </div>
            </div>
        </template>
    </Dropdown>
</template>

<style scoped>
.icon-input {
    display: flex;
    align-items: flex-start;
    /* no gap: the contenteditable inside TextInput already adds its own 2px of
       left padding, which is exactly the margin-right the other rows put on their icon */
    gap: 0px;
    width: 100%;
    /* same frame as the text search bar (TextSearchInput.vue), but invisible until focused:
       the border is always there so showing it costs no geometry */
    padding: 2px 0px;
    border: 1px solid transparent;
    background-color: white;
    border-radius: 3px;
    transition: border-color 0.2s;
    /* pulls the frame back out by its own border + padding, so the icon glyph stays at the
       exact x of the plain PropertyIcon on the other property rows */
    font-size: 14px;
    /* explicit: the popup is teleported out of the row, so it must not inherit
       the row line-height, otherwise the text sits at a different height once focused.
       18 + 4 padding + 2 border = 24, so the frame still fits the 26px row uncropped */
    line-height: 18px;
    cursor: text;
    margin-left: 1px;
}

/* focus: blue frame, like the search bar */
.highlight {
    border-color: var(--blue);
}

/* the expanded popup floats above the row, so it keeps an elevation shadow to lift it
   off whatever it covers */
.icon-input-popup {
    box-shadow: 0px 1px 2px rgba(0, 0, 0, 0.10),
                0px 2px 6px rgba(0, 0, 0, 0.16);
}

/* while the popup overlays it, the collapsed box keeps its size but stays hidden */
.invisible-content {
    visibility: hidden;
}

.icon-zone {
    flex: 0 0 auto;
    /* no box around the glyph: it must sit at the exact same x as the plain
       PropertyIcon of the other property rows */
    display: inline-flex;
    align-items: center;
    height: 18px;
    color: var(--grey-text);
    cursor: pointer;
}

.icon-zone:hover {
    color: black;
}

.field-zone {
    flex: 1 1 auto;
    min-width: 0;
}

/* Collapsed state: the row is a fixed 26px slot, so the text must never wrap — long values
   are clipped here and only the popup shows them in full. */
.single-line {
    max-height: 18px;
    overflow: hidden;
}

.single-line :deep(.contenteditable) {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

/* past max-height the text scrolls instead of growing the popup further */
.scroll-zone {
    overflow-y: auto;
    overflow-x: hidden;
}

.scroll-zone::-webkit-scrollbar {
    width: 6px;
}

.scroll-zone::-webkit-scrollbar-thumb {
    background: rgba(0, 0, 0, 0.2);
    border-radius: 3px;
}

.scroll-zone::-webkit-scrollbar-track {
    background: transparent;
}
</style>

<!-- Not scoped: the popup is teleported and wrapped by floating-vue's own frame, whose
     default theme adds a 1px border, a background and a shadow. That border alone shifts
     the content by 1px and would break the "nothing moves" overlay. :has() keeps the rule
     limited to the frames that actually contain one of our popups. -->
<style>
.v-popper__inner:has(.icon-input-popup),
.v-popper__inner .popup:has(.icon-input-popup) {
    border: none !important;
    background: transparent !important;
    box-shadow: none !important;
    /* the frame ships overflow-y:auto and gets a max-height from the positioning engine,
       which cropped the box as soon as the text wrapped to a second line. Height is our
       own business here: .scroll-zone owns the cap. */
    overflow: visible !important;
    max-height: none !important;
}

/* The popup is an overlay of something already on screen, not an apparition: the
   default 150ms opacity fade shows the (already hidden) collapsed box through it,
   which reads as a flash. Swap instantly instead. */
.v-popper__popper:has(.icon-input-popup),
.v-popper__popper:has(.icon-input-popup) > .v-popper__wrapper {
    transition: none !important;
}

.v-popper__popper:has(.icon-input-popup) .v-popper__arrow-container {
    display: none;
}
</style>
