<script setup lang="ts">
// Function picker + parameter form + cancel/call bar of an action. Shared by the
// dropdown and the view-modal presentations of ActionButton2. With a `title` it draws
// the whole modal panel (header with close button, footer with the status), styled like
// the island tool windows: a 30px header in small capitals (PropertyPanel's .tw-header),
// a two-column "label | field" form, flat 26px controls and buttons.
//
// No `position` / `transform` on any element here: the non-teleported dropdowns of the
// params (vector type, property) are absolutely positioned against the view modal's
// backdrop, and a positioned ancestor would get them clipped by the scrolling body.
import { computed, nextTick, ref } from 'vue'
import { ParamDescription } from '@/data/models'
import ParamInput from '../inputs/ParamInput.vue'
import Dropdown from '../dropdowns/Dropdown.vue'
import { useActionStore } from '@/data/stores/actionStore'
import { sourceFromFunction, objValues, isParamVisible, prettifyName } from '@/utils/utils'

const actions = useActionStore()

const props = defineProps<{
    action: string
    inputs: ParamDescription[]
    width?: number
    // Modal presentation: header with this title and a close button.
    title?: string
    // An earlier run is still pending: the call button is disabled.
    busy?: boolean
    // Modal presentation: the run submitted from this form is in flight — inputs and the
    // function picker are locked, Enter is ignored, the footer says so.
    running?: boolean
    // Modal presentation: why the last submitted run failed, shown in the footer.
    error?: string | null
}>()
const localFunction = defineModel<string>('func')
const emits = defineEmits(['call', 'cancel'])

const ACTION_ICONS: Record<string, string> = {
    group: 'intersect',
    execute: 'terminal',
    similar: 'images',
    find_similar: 'images',
    map: 'map',
    import: 'box-arrow-in-down',
    export: 'box-arrow-up'
}

const isModal = computed(() => !!props.title)
const actionIcon = computed(() => ACTION_ICONS[props.action] ?? 'boxes')
const source = computed(() => localFunction.value ? sourceFromFunction(localFunction.value) : '')

function describe(id: string) {
    const f = actions.index[id]
    return {
        id,
        label: f?.label || prettifyName(f?.name || id.slice(id.indexOf('.') + 1)),
        source: sourceFromFunction(id),
        description: f?.description || ''
    }
}

const available = computed(() =>
    objValues(actions.index).filter(a => a.hooks.includes(props.action)).map(a => describe(a.id))
)
const current = computed(() =>
    localFunction.value && actions.index[localFunction.value] ? describe(localFunction.value) : null
)
const visibleInputs = computed(() => props.inputs.filter(i => isParamVisible(i, props.inputs)))
const canCall = computed(() => !!current.value && !props.busy)

const fnDropdown = ref<InstanceType<typeof Dropdown>>()
const fnButton = ref<HTMLElement>()

function selectFunction(func: string, hide: () => void) {
    localFunction.value = func
    hide()
}

// The function list takes the focus while open; give it back to the trigger when it closes
// (unless the user clicked into another field), so Enter / Esc keep working in the form.
function onFnListHidden() {
    nextTick(() => {
        const a = document.activeElement
        if (!a || a === document.body) fnButton.value?.focus()
    })
}

function paramLabel(input: ParamDescription) {
    return input.label || prettifyName(input.name)
}

function toggleBool(input: ParamDescription) {
    input.defaultValue = !input.defaultValue
}

function call() {
    if (!canCall.value) return
    emits('call')
}

// Enter anywhere in the form submits. Buttons handle Enter themselves (native click), and
// the dropdowns inside stop it in their popup.
function onEnter(e: KeyboardEvent) {
    const t = e.target as HTMLElement
    if (e.isComposing || t.closest('button, textarea')) return
    e.preventDefault()
    call()
}

defineExpose({ reset: () => { fnDropdown.value?.hide() } })
</script>

<template>
    <div class="af" :class="[isModal ? 'af-modal' : 'af-dropdown', { 'af-running': props.running }]"
        :style="props.width ? { width: props.width + 'px' } : undefined" @keydown.enter="onEnter">
        <!-- Tool-window header: small-caps title, close action -->
        <div v-if="isModal" class="af-head">
            <span class="af-title"><i :class="'bi bi-' + actionIcon" />{{ props.title }}</span>
            <button type="button" class="af-close" :title="$t('close')" @click="emits('cancel')">
                <i class="bi bi-x-lg" />
            </button>
        </div>

        <form class="af-body" @submit.prevent="">
            <div class="af-grid">
                <!-- Function: a combo box like the other fields, the list opens in a popup -->
                <div class="af-label">{{ $t('action_modal.function') }}</div>
                <div class="af-field af-fn-row">
                    <Dropdown v-if="available.length > 1 || (available.length && !current)" ref="fnDropdown"
                        class="af-fn-dd" :teleport="true" placement="bottom-start" :fit-content="true"
                        @hide="onFnListHidden">
                        <template #button>
                            <button ref="fnButton" type="button" class="af-combo" :title="localFunction">
                                <span class="af-combo-label">{{ current?.label ?? $t('no_function_available') }}</span>
                                <span v-if="current" class="af-combo-source">{{ source }}</span>
                                <i class="bi bi-chevron-down af-combo-chevron" />
                            </button>
                        </template>
                        <template #popup="{ hide }">
                            <div class="af-fn-list">
                                <div v-for="f in available" :key="f.id" class="af-fn-item"
                                    :class="{ selected: f.id === localFunction }" :title="f.id"
                                    @click="selectFunction(f.id, hide)">
                                    <div class="af-fn-item-top">
                                        <span class="af-fn-item-name">{{ f.label }}</span>
                                        <span class="af-fn-item-src">{{ f.source }}</span>
                                    </div>
                                    <div v-if="f.description" class="af-fn-item-desc">{{ f.description }}</div>
                                </div>
                            </div>
                        </template>
                    </Dropdown>
                    <!-- Single function: shown, nothing to pick -->
                    <div v-else-if="current" class="af-combo af-combo-static" :title="localFunction">
                        <span class="af-combo-label">{{ current.label }}</span>
                        <span class="af-combo-source">{{ source }}</span>
                    </div>
                    <div v-else class="af-empty">{{ $t('no_function_available') }}</div>
                    <div v-if="current?.description" class="af-help" :title="current.description">
                        {{ current.description }}
                    </div>
                </div>

                <div v-if="visibleInputs.length" class="af-sep" />

                <fieldset :disabled="props.running" class="af-fieldset">
                <template v-for="input in visibleInputs" :key="input.name">
                    <!-- Checkbox: in the field column, its label beside it -->
                    <template v-if="input.type == 'bool'">
                        <div class="af-label" />
                        <div class="af-field">
                            <div class="af-check">
                                <div class="af-control"><ParamInput :input="input" :source="source" hide-label /></div>
                                <span class="af-check-label" :title="input.name" @click="toggleBool(input)">
                                    {{ paramLabel(input) }}
                                </span>
                            </div>
                            <div v-if="input.description" class="af-help af-check-help" :title="input.description">
                                {{ input.description }}
                            </div>
                        </div>
                    </template>
                    <template v-else>
                        <div class="af-label" :title="input.name">{{ paramLabel(input) }}</div>
                        <div class="af-field">
                            <div class="af-control"><ParamInput :input="input" :source="source" hide-label /></div>
                            <div v-if="input.description" class="af-help" :title="input.description">
                                {{ input.description }}
                            </div>
                        </div>
                    </template>
                </template>
                </fieldset>
            </div>
        </form>

        <div class="af-foot">
            <div v-if="isModal && props.error" class="af-status af-error" :title="props.error">
                <i class="bi bi-exclamation-circle" /> {{ $t('action_modal.error') }} : {{ props.error }}
            </div>
            <div v-else-if="isModal && props.running" class="af-status">
                <span class="spinner-border spinner-border-sm" role="status" /> {{ $t('action_modal.pending') }}
            </div>
            <div class="af-actions">
                <button type="button" class="af-btn" @click="emits('cancel')">
                    {{ $t('cancel') }}<kbd v-if="isModal" class="af-key">Esc</kbd>
                </button>
                <button type="button" class="af-btn af-btn-primary" :disabled="!canCall" data-autofocus
                    @click="call">
                    <span v-if="props.busy && !props.running" class="spinner-border spinner-border-sm" role="status" />
                    {{ $t('call') }}<kbd v-if="isModal" class="af-key">↵</kbd>
                </button>
            </div>
        </div>
    </div>
</template>

<style scoped>
/* Same vocabulary as the island panels (theme.css, PropertyPanel .tw-*): 30px header,
   12px/13px type, 4px radii, 1px borders, no glow, no tinted surfaces. */
.af {
    display: flex;
    flex-direction: column;
    min-height: 0;
    max-width: 100%;
    /* no background: the (rounded, unclipped) panel or popup provides it */
    color: var(--text-primary);
    font-size: 13px;
    cursor: default;
}

/* ---- Header (tool-window style) ---- */
.af-head {
    flex: 0 0 auto;
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 30px;
    padding: 0 4px 0 12px;
}

.af-title {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    min-width: 0;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-semibold);
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.02em;
}

.af-title .bi {
    font-size: 13px;
}

.af-close {
    flex: 0 0 auto;
    width: 22px;
    height: 22px;
    padding: 0;
    border: none;
    border-radius: var(--radius-sm) !important;
    background: none;
    color: var(--text-tertiary);
    font-size: 11px !important;
}

.af-close:hover {
    background-color: var(--hover-bg);
    color: var(--text-primary);
}

/* ---- Body: "label | field" grid ---- */
/* Scrolls when the panel is taller than the view area (header and footer stay). */
.af-body {
    flex: 1 1 auto;
    min-height: 0;
    overflow-y: auto;
    margin: 0;
    padding: 6px 12px 12px;
}

.af-dropdown .af-body {
    padding: 10px 10px 10px;
}

.af-grid {
    display: grid;
    grid-template-columns: fit-content(38%) minmax(0, 1fr);
    column-gap: 12px;
    row-gap: 8px;
    align-items: start;
}

.af-fieldset {
    display: contents;
    min-width: 0;
    margin: 0;
    padding: 0;
    border: 0;
}

/* Run in flight: the form is locked (fieldset disables the native controls; this catches the
   custom ones and the function picker). */
.af-running .af-fieldset,
.af-running .af-fn-row {
    pointer-events: none;
    opacity: 0.6;
}

.af-sep {
    grid-column: 1 / -1;
    height: 1px;
    margin: 2px 0;
    background-color: var(--border-light);
}

/* Centered on the first line of its field (the 26px control). */
.af-label {
    display: flex;
    align-items: center;
    min-height: 26px;
    color: var(--text-secondary);
    line-height: 1.25;
    overflow-wrap: anywhere;
}

.af-field {
    display: flex;
    flex-direction: column;
    gap: 3px;
    min-width: 0;
}

.af-help {
    font-size: 11.5px;
    line-height: 1.35;
    color: var(--text-tertiary);
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}

.af-check {
    display: flex;
    align-items: center;
    gap: 6px;
    min-height: 26px;
}

.af-check-label {
    cursor: pointer;
    user-select: none;
}

.af-check-help {
    padding-left: 20px;
}

/* ---- Function combo box ---- */
.af-fn-dd {
    min-width: 0;
    max-width: 100%;
}

.af-combo {
    box-sizing: border-box;
    display: flex;
    align-items: center;
    gap: 6px;
    width: 100%;
    height: 26px;
    padding: 0 8px;
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm) !important;
    background: var(--bg-primary);
    font-size: 13px !important;
    color: var(--text-primary);
    white-space: nowrap;
    cursor: pointer;
}

/* global `button { display: flex !important; justify-content: center !important }` */
button.af-combo {
    justify-content: flex-start !important;
}

.af-combo:hover {
    border-color: var(--border-dark);
}

.af-combo:focus-visible {
    border-color: var(--primary);
    box-shadow: 0 0 0 1px var(--primary);
}

.af-combo-static {
    background: var(--bg-secondary);
    border-color: var(--border-light);
    cursor: default;
}

.af-combo-static:hover {
    border-color: var(--border-light);
}

.af-combo-label {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
}

.af-combo-source {
    flex: 0 1 auto;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    font-size: 12px;
    color: var(--text-tertiary);
}

.af-combo-chevron {
    flex: 0 0 auto;
    margin-left: auto;
    font-size: 10px;
    color: var(--text-secondary);
}

.af-empty {
    display: flex;
    align-items: center;
    min-height: 26px;
    color: var(--text-tertiary);
}

/* Function list (teleported popup) */
.af-fn-list {
    min-width: 240px;
    max-width: 380px;
    max-height: 320px;
    overflow-y: auto;
    padding: 4px;
    font-size: 13px;
}

.af-fn-item {
    padding: 4px 8px;
    border-radius: var(--radius-sm);
    cursor: pointer;
}

.af-fn-item:hover {
    background-color: var(--hover-bg);
}

.af-fn-item.selected {
    background-color: var(--primary-light);
}

.af-fn-item.selected .af-fn-item-name {
    color: var(--primary);
}

.af-fn-item-top {
    display: flex;
    align-items: baseline;
    gap: 8px;
    white-space: nowrap;
}

.af-fn-item-name {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
}

.af-fn-item-src {
    flex: 0 0 auto;
    margin-left: auto;
    font-size: 11px;
    color: var(--text-tertiary);
}

.af-fn-item-desc {
    font-size: 11.5px;
    line-height: 1.35;
    color: var(--text-secondary);
    white-space: normal;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}

/* ---- Controls rendered by ParamInput ----
   Full width, 26px, 4px radius. Scoped to this form, ParamInput keeps its look elsewhere. */
.af-control {
    display: flex;
    min-width: 0;
}

.af-check .af-control {
    flex: 0 0 auto;
}

.af-control :deep(.input-cell) {
    flex: 1 1 auto;
    min-width: 0;
}

.af-control :deep(.input-cell > *) {
    flex: 1 1 auto;
    min-width: 0;
}

.af-control :deep(input[type="text"]),
.af-control :deep(input[type="number"]),
.af-control :deep(select) {
    box-sizing: border-box;
    width: 100%;
    height: 26px;
    padding: 0 8px !important;
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    background: var(--bg-primary);
    font-size: 13px !important;
    line-height: normal;
    color: var(--text-primary);
}

.af-control :deep(input[type="number"]) {
    font-variant-numeric: tabular-nums;
}

.af-control :deep(input[type="file"]) {
    width: 100%;
    font-size: 12px !important;
}

.af-control :deep(input[type="text"]:hover),
.af-control :deep(input[type="number"]:hover),
.af-control :deep(select:hover) {
    border-color: var(--border-dark);
}

.af-control :deep(input[type="text"]:focus),
.af-control :deep(input[type="number"]:focus),
.af-control :deep(select:focus) {
    border-color: var(--primary);
    box-shadow: 0 0 0 1px var(--primary);
}

.af-control :deep(input[type="checkbox"]) {
    width: 14px;
    height: 14px;
    margin: 0;
    accent-color: var(--primary);
    cursor: pointer;
}

/* Dropdown triggers (vector type, property): look like the inputs */
.af-control :deep(.sbb) {
    box-sizing: border-box;
    display: flex;
    align-items: center;
    min-height: 26px;
    padding: 0 8px;
    border-radius: var(--radius-sm);
    background: var(--bg-primary);
    font-size: 13px !important;
}

.af-control :deep(.sbb > *) {
    flex: 1 1 auto;
    min-width: 0;
}

/* Path input: field + browse button */
.af-control :deep(.path-input) {
    gap: 6px;
}

.af-control :deep(.browse) {
    display: flex;
    align-items: center;
    height: 26px;
    padding: 0 8px;
    border-radius: var(--radius-sm);
}

/* ---- Footer: status left, buttons right ---- */
.af-foot {
    flex: 0 0 auto;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 12px;
    border-top: 1px solid var(--border-light);
}

.af-dropdown .af-foot {
    padding: 8px 10px;
}

.af-status {
    display: flex;
    align-items: center;
    gap: 6px;
    flex: 1 1 auto;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 12px;
    color: var(--text-secondary);
}

.af-status .spinner-border {
    flex: 0 0 auto;
    width: 11px;
    height: 11px;
    border-width: 1.5px;
    color: var(--primary);
}

.af-error {
    display: block;
    color: var(--error);
}

.af-actions {
    display: flex;
    gap: 6px;
    margin-left: auto;
}

.af-btn {
    gap: 6px;
    height: 26px;
    min-width: 72px;
    padding: 0 12px;
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm) !important;
    background: var(--bg-primary);
    font-size: 13px !important;
    color: var(--text-primary);
    white-space: nowrap;
    transition: background-color var(--transition-fast), border-color var(--transition-fast);
}

.af-btn:hover:not(:disabled) {
    background-color: var(--hover-bg);
}

.af-btn:focus-visible {
    border-color: var(--primary);
    box-shadow: 0 0 0 1px var(--primary);
}

.af-btn-primary {
    border-color: var(--primary);
    background: var(--primary);
    color: var(--text-inverse);
}

.af-btn-primary:hover:not(:disabled) {
    border-color: var(--primary-dark);
    background-color: var(--primary-dark);
}

.af-btn-primary:focus-visible {
    box-shadow: 0 0 0 1px var(--bg-primary), 0 0 0 2px var(--primary);
}

/* Key hint inside a button: flat, quiet, same height as the text */
.af-key {
    display: inline-block;
    min-width: 16px;
    margin: 0 -4px 0 2px;
    padding: 0 4px;
    border: none;
    border-radius: 3px;
    background: var(--bg-tertiary);
    box-shadow: none;
    font-family: inherit;
    font-size: 11px;
    font-weight: 400;
    line-height: 16px;
    text-align: center;
    color: var(--text-tertiary);
}

.af-btn-primary .af-key {
    background: rgba(255, 255, 255, 0.18);
    color: rgba(255, 255, 255, 0.85);
}

.af-btn-primary .spinner-border {
    width: 11px;
    height: 11px;
    border-width: 1.5px;
}
</style>
