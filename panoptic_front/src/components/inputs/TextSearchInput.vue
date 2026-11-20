<script setup lang="ts">
import { useActionStore } from '@/data/stores/actionStore';
import { ref, watch, computed, onMounted, inject, nextTick } from 'vue'
import SelectDropdown from '../dropdowns/SelectDropdown.vue';
import { keyState } from '@/data/composables/keyState';
import InputOptions from '../actions/InputOptions.vue';
import { SelectOption, TextQuery } from '@/data/models';
import LoadWheel from '../loading/LoadWheel.vue';
import { TabManager } from '@/core/TabManager';
import { CollectionManager } from '@/core/CollectionManager';
import ViewModal from '../utils/ViewModal.vue';
import Dropdown from '../dropdowns/Dropdown.vue';
import { viewModalScopeKey } from '@/data/composables/viewModal';

const actions = useActionStore()

const props = defineProps<{ tab: TabManager, size?: number, collection?: CollectionManager }>()
const emits = defineEmits(['update:query'])

// The collection this search controls — the per-view one when provided
// (FilterPanel), else the tab's primary collection.
const collection = computed(() => props.collection ?? props.tab.collection)

// Inside a view the search is edited in a modal centered over the view area and
// applied on Enter; elsewhere it stays an inline input applied on blur / Enter.
const modalScope = inject(viewModalScopeKey, null)
const isModal = modalScope !== null
const modalOpen = ref(false)

const inputElem = ref(null)
const isFocus = ref(false)

const defaultModes = [{ value: 'text', icon: 'search' }, { value: 'regex', icon: 'regex' }]
const modeOptions = ref<SelectOption[]>([])
const mode = ref('text')
const searchText = ref('')
const size = computed(() => props.size ?? 26)
// A search is running for this collection (FilterManager.queryStatus).
const isLoading = computed(() => collection.value.filterManager.queryStatus.running > 0)

const isPluginMode = computed(() => mode.value != 'text' && mode.value != 'regex')

function updateModes() {
    const fncs = actions.textSearchFunctions.map(f => ({
        value: f.id,
        icon: 'boxes'
    }))
    modeOptions.value = [...defaultModes, ...fncs]
}

function loadFromProps() {
    if (!collection.value.filterManager.state.query) return
    mode.value = collection.value.filterManager.state.query.type || 'text'
    searchText.value = collection.value.filterManager.state.query.text || ''
}

// The query currently applied (shown on the modal-mode trigger).
const appliedText = computed(() => collection.value.filterManager.state.query?.text ?? '')

function openSearch() {
    loadFromProps()
    searchError.value = null
    modalOpen.value = true
}

// Closing without Enter drops the draft.
function onModalClosed() {
    searchText.value = appliedText.value
    loadFromProps()
}

// Modal mode chips: Text / Regex / Semantic. Semantic covers every plugin
// text-search function; the function itself is picked in a second row.
const SEMANTIC = 'semantic'
const pluginFunctions = computed(() => actions.textSearchFunctions.map(f => ({
    value: f.id,
    label: f.label || prettifyName(f.name || f.id),
    title: f.description || f.id
})))
const modeChips = computed(() => [
    { value: 'text', icon: 'search', labelKey: 'main.menu.search_mode_text' },
    { value: 'regex', icon: 'regex', labelKey: 'main.menu.search_mode_regex' }
])
const currentPluginLabel = computed(() => pluginFunctions.value.find(f => f.value === mode.value)?.label ?? '')
const activeChip = computed(() => isPluginMode.value ? SEMANTIC : mode.value)
// Last plugin function used, so Semantic comes back to it.
let lastPlugin: string | null = null
watch(mode, (m) => { if (isPluginMode.value) lastPlugin = m }, { immediate: true })

function prettifyName(name: string) {
    const s = name.replace(/_/g, ' ').trim()
    return s.charAt(0).toUpperCase() + s.slice(1)
}

const modalInput = ref<HTMLInputElement | null>(null)

// Switching mode only changes the draft (applied on Enter); keep typing focus.
function selectMode(value: string) {
    if (value === SEMANTIC) {
        if (isPluginMode.value) return modalInput.value?.focus()
        const ids = pluginFunctions.value.map(f => f.value)
        value = lastPlugin && ids.includes(lastPlugin) ? lastPlugin : ids[0]
        if (!value) return
    }
    mode.value = value
    modalInput.value?.focus()
}

function clearDraft() {
    searchText.value = ''
    modalInput.value?.focus()
}

// Modal submit: the modal stays open (input read-only, spinner + "Searching...") until the
// reload this query triggers has applied its results, then closes. On failure it stays open
// with the error. Esc / backdrop while pending just closes it: the search keeps running (there
// is no cancellation down to the backend) and the trigger's loader shows it.
const submitting = ref(false)
const searchError = ref<string | null>(null)
let submitSeq = 0

async function submitFromModal() {
    if (submitting.value) return
    searchError.value = null
    const query = buildQuery()
    if (!query || areQueryEquals(query, collection.value.filterManager.state.query)) {
        modalOpen.value = false
        return
    }
    const seq = ++submitSeq
    submitting.value = true
    try {
        await collection.value.applyQuery(query)
        if (seq === submitSeq) modalOpen.value = false
    } catch (e: any) {
        if (seq === submitSeq) searchError.value = e?.message ? String(e.message) : String(e)
    } finally {
        if (seq === submitSeq) submitting.value = false
    }
}

function resetSearch() {
    searchText.value = ''
    emitQuery()
}

function confirmSearch() {
    emitQuery()
}

function emitQuery() {
    const query = buildQuery()
    if (query) setQuery(query)
}

// The query for the current draft, or null when the plugin mode vanished (then reset to text).
function buildQuery(): TextQuery | null {
    const newQuery: TextQuery = {
        type: mode.value,
        text: searchText.value
    }

    if (isPluginMode.value) {
        if (!actions.index[mode.value]) {
            mode.value = 'text'
            resetSearch()
            return null
        }
        const ctx = actions.getContext(mode.value)
        ctx.uiInputs['text'] = searchText.value
        // The search box keeps every scored image: no similarity threshold.
        if ('min_similarity' in ctx.uiInputs) ctx.uiInputs['min_similarity'] = 0
        newQuery.ctx = ctx
    }

    return newQuery
}

function setQuery(query) {
    if(areQueryEquals(query, collection.value.filterManager.state.query)) return
    // Mutating the query triggers the CollectionManager's filter watch, which
    // debounces + recomputes (Pillar B). Persistence is handled by autosave.
    collection.value.filterManager.setQuery(query)
}

function areQueryEquals(query1: TextQuery, query2: TextQuery) {
    if(!query1 || !query2) return false
    if(query1.type != query2.type) return false
    if(query1.text != query2.text) return false
    if(JSON.stringify(query1.ctx?.uiInputs) !== JSON.stringify(query2.ctx?.uiInputs)) return false
    return true
}

updateModes()
watch(() => collection.value.filterManager.state.query, loadFromProps, { deep: true })
watch(() => actions.textSearchFunctions, updateModes)
watch(mode, () => { if (!isModal) emitQuery() })
onMounted(() => {
    updateModes()
    loadFromProps()
})

keyState.ctrlF.on(() => {
    if (!isModal) return inputElem.value?.focus()
    // Only one search modal: the first view's (or the shared one).
    if (modalScope === 0 || modalScope === 'all') openSearch()
})

</script>

<template>
    <!-- View mode: a compact trigger showing the applied query; editing happens in a modal -->
    <div v-if="isModal" class="trigger" :class="{ 'chip-active': appliedText }" @click="openSearch"
        :title="$t('main.menu.search')">
        <i class="bi bi-search" />
        <span v-if="!appliedText">{{ $t('main.menu.search_short') }}</span>
        <span v-else class="trigger-text">{{ appliedText }}</span>
        <LoadWheel v-if="isLoading" :loading="isLoading" />
        <i v-if="appliedText" class="bi bi-x trigger-clear" @click.stop="resetSearch" />
        <ViewModal v-model:show="modalOpen" :scope="modalScope" :width="600" bare placement="top"
            @close="onModalClosed">
            <div class="spot">
                <div class="spot-bar">
                    <i class="bi bi-search spot-icon" />
                    <input ref="modalInput" class="spot-input" type="text"
                        v-model="searchText" :placeholder="$t('main.menu.search')" spellcheck="false"
                        autocomplete="off" :readonly="submitting" :class="{ pending: submitting }"
                        @keydown.enter.prevent="submitFromModal" />
                    <div v-if="isLoading || submitting" class="spot-loading"><LoadWheel :loading="true" /></div>
                    <button v-if="searchText.length && !submitting" type="button" class="spot-clear" tabindex="-1"
                        :title="$t('main.menu.search_clear')" @mousedown.prevent @click="clearDraft">
                        <i class="bi bi-x-circle-fill" />
                    </button>
                </div>
                <div class="spot-footer">
                    <div class="spot-modes" :class="{ disabled: submitting }">
                        <button v-for="c in modeChips" :key="c.value" type="button" class="spot-mode"
                            :class="{ active: activeChip === c.value }"
                            @mousedown.prevent @click="selectMode(c.value)">
                            <i :class="'bi bi-' + c.icon" />
                            <span class="spot-mode-label">{{ $t(c.labelKey) }}</span>
                        </button>
                        <!-- Semantic: click = last used function; the chevron opens the function list -->
                        <div v-if="pluginFunctions.length" class="spot-split" :class="{ active: isPluginMode }">
                            <button type="button" class="spot-mode" :title="isPluginMode ? currentPluginLabel : undefined"
                                @mousedown.prevent @click="selectMode(SEMANTIC)">
                                <i class="bi bi-boxes" />
                                <span class="spot-mode-label">{{ $t('main.menu.search_mode_semantic') }}</span>
                                <span v-if="isPluginMode" class="spot-fn">{{ currentPluginLabel }}</span>
                            </button>
                            <Dropdown :teleport="true" placement="bottom-end" :fit-content="true" :auto-focus="false">
                                <template #button>
                                    <button type="button" class="spot-mode spot-handle" @mousedown.prevent>
                                        <i class="bi bi-chevron-down" />
                                    </button>
                                </template>
                                <template #popup="{ hide }">
                                    <div class="fn-list">
                                        <div v-for="f in pluginFunctions" :key="f.value" class="fn-item"
                                            :class="{ selected: mode === f.value }" :title="f.title"
                                            @mousedown.prevent @click="selectMode(f.value); hide()">
                                            <i class="bi bi-boxes" />
                                            <span>{{ f.label }}</span>
                                        </div>
                                    </div>
                                </template>
                            </Dropdown>
                        </div>
                    </div>
                    <div v-if="searchError" class="spot-error" :title="searchError">
                        <i class="bi bi-exclamation-triangle" /> {{ $t('main.menu.search_error') }}: {{ searchError }}
                    </div>
                    <InputOptions v-if="isPluginMode" :key="mode" :function-id="mode" :size="14"
                        class="spot-options" :class="{ disabled: submitting }" :hide-text="true" />
                    <div v-if="submitting" class="spot-hints">{{ $t('main.menu.search_pending') }}</div>
                    <div v-else class="spot-hints">
                        <span><kbd>↵</kbd> {{ $t('call') }}</span>
                        <span><kbd>Esc</kbd> {{ $t('main.menu.search_close') }}</span>
                    </div>
                </div>
            </div>
        </ViewModal>
    </div>

    <div v-else class="cont3" :class="{ focus: isFocus }" :style="{ height: size + 'px' }">
        <div class="select-wrapper">
            <SelectDropdown :options="modeOptions" v-model="mode" placeholder="Search Mode" :no-border="true"
                :icon-only="true" :size="size * 0.6" :teleport="false" />
        </div>
        <div class="input-field d-flex align-items-center">
            <!-- Wide enough for the whole placeholder (+2ch for the caret and the clear button),
                 in whatever language it is shown. -->
            <input class="text-input2" type="text" v-model="searchText"
                :style="{ height: size + 'px', minWidth: ($t('main.menu.search').length + 2) + 'ch' }"
                :placeholder="$t('main.menu.search')" ref="inputElem" @focusin="isFocus = true"
                @focusout="isFocus = false" @blur="confirmSearch"
                @keypress.enter="t => (t.target as HTMLElement).blur()" />
            <div class="toolbar">
                <div v-if="isLoading" :style="{ fontSize: size * 0.63 + 'px' }" style="margin-right: 2px;">
                    <LoadWheel :loading="isLoading" />
                </div>
                <div v-if="searchText.length" :style="{ fontSize: size * 0.63 + 'px' }" style="margin-right: 2px;"
                    @click="resetSearch"><i class="bi bi-x sb" /></div>
            </div>

        </div>
        <div v-if="isPluginMode" class="options-wrapper">
            <InputOptions :function-id="mode" :size="props.size * 0.6" :style="{ fontSize: size * 0.56 + 'px' }"
                :hide-text="true" @changed="emitQuery" />
        </div>
    </div>
</template>

<style scoped>
.cont3 {
    display: flex;
    align-items: center;
    border: 1px solid var(--border-color, #ccc);
    background-color: var(--grey, #f8f8f8);
    border-radius: 3px;
    transition: border-color 0.2s, box-shadow 0.2s;
    padding: 0 0px;
    overflow: hidden;
    /* Sized by its content: the mode select plus an input as wide as its placeholder. A
       shrinking or capped box clipped the placeholder. */
    flex: 0 0 auto;
}

.cont3:hover {
    border-color: #999;
}

.cont3.focus {
    border-color: var(--blue);
}

.select-wrapper {
    display: flex;
    align-items: center;
    padding: 0 0px;
    /* Long function labels shrink (with ellipsis) so the input keeps room */
    flex: 0 1 auto;
    min-width: 0;
    max-width: 50%;
    overflow: hidden;
}

.divider {
    width: 1px;
    background-color: var(--border-color, #ccc);
    flex-shrink: 0;
    margin: 0 2px;
}

.options-wrapper {
    display: flex;
    flex-shrink: 0;
    align-items: center;
}

.toolbar {
    display: flex;
    position: absolute;
    right: 0px;
    /* top: 0px; */
}

.input-field {
    padding: 0;
    position: relative;
    flex: 1 0 auto;
}

.text-input2 {
    border: none;
    background-color: transparent;
    outline: none;
    width: 100%;
}
/* Compact trigger, plain like the "Filtrer:" / "Grouper:" labels next to it */
.trigger {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 1px 4px;
    border-radius: 2px;
    cursor: pointer;
    white-space: nowrap;
    flex: 0 0 auto;
}

.trigger:hover {
    background-color: var(--hover-bg, #f0f0f0);
}

.trigger-text {
    max-width: 18ch;
    overflow: hidden;
    text-overflow: ellipsis;
}

.trigger-clear {
    opacity: 0.6;
}

.trigger-clear:hover {
    opacity: 1;
}

/* Spotlight-like modal search */
.spot {
    display: flex;
    flex-direction: column;
    cursor: default;
}

.spot-bar {
    display: flex;
    align-items: center;
    gap: 12px;
    height: 56px;
    padding: 0 14px 0 18px;
}

.spot-icon {
    flex: 0 0 auto;
    font-size: 20px;
    color: var(--text-tertiary, #999);
}

.spot-input {
    flex: 1 1 auto;
    min-width: 0;
    height: 100%;
    padding: 0;
    border: none;
    outline: none;
    box-shadow: none;
    background: transparent;
    font-size: 21px;
    color: var(--text-primary, #1a1a1a);
}

.spot-input::placeholder {
    color: var(--text-tertiary, #999);
}

.spot-input.pending {
    color: var(--text-tertiary, #999);
}

.spot-modes.disabled,
.spot-options.disabled {
    pointer-events: none;
    opacity: 0.5;
}

.spot-error {
    flex: 1 1 100%;
    order: -1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--danger, #c0392b);
}

.spot-loading {
    flex: 0 0 auto;
    display: flex;
    align-items: center;
}

.spot-clear {
    flex: 0 0 auto;
    display: flex;
    align-items: center;
    padding: 2px;
    border: none;
    background: transparent;
    font-size: 16px;
    line-height: 1;
    color: var(--text-tertiary, #999);
    cursor: pointer;
}

.spot-clear:hover {
    color: var(--text-secondary, #666);
}

/* Slim secondary row: mode, plugin options, keyboard hints. Not clipped (the plugin
   options popup renders inside it). */
.spot-footer {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px 10px;
    padding: 6px 10px;
    border-top: 1px solid var(--border-light, #e8e8e8);
    background: #fafbfc;
    border-radius: 0 0 12px 12px;
    font-size: 12px;
}

.spot-modes {
    display: flex;
    gap: 2px;
    padding: 2px;
    min-width: 0;
    max-width: 100%;
    overflow-x: auto;
    scrollbar-width: none;
    background: var(--hover-bg, #f0f0f0);
    border-radius: 7px;
}

.spot-mode {
    display: inline-flex;
    font-family: inherit;
    align-items: center;
    gap: 5px;
    flex: 0 0 auto;
    padding: 2px 9px;
    border: none;
    border-radius: 5px;
    background: transparent;
    font-size: 12px;
    line-height: 18px;
    color: var(--text-secondary, #666);
    white-space: nowrap;
    cursor: pointer;
}

.spot-mode:hover {
    color: var(--text-primary, #1a1a1a);
}

.spot-mode.active {
    background: white;
    color: var(--primary, #1678c2);
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.12);
}

.spot-mode-label {
    max-width: 16ch;
    overflow: hidden;
    text-overflow: ellipsis;
}

/* Semantic split button: main part + chevron handle */
.spot-split {
    display: inline-flex;
    align-items: center;
    border-radius: 5px;
}

.spot-split.active {
    background: white;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.12);
}

.spot-split.active .spot-mode {
    color: var(--primary, #1678c2);
}

.spot-handle {
    padding: 2px 6px;
    border-left: 1px solid var(--border-light, #e0e0e0);
    border-radius: 0 5px 5px 0;
    font-size: 10px;
}

.spot-fn {
    max-width: 18ch;
    overflow: hidden;
    text-overflow: ellipsis;
    opacity: 0.75;
}

.fn-list {
    max-height: 300px;
    min-width: 200px;
    overflow-y: auto;
    padding: 4px;
    font-size: 13px;
}

.fn-item {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 8px;
    border-radius: 4px;
    cursor: pointer;
    white-space: nowrap;
}

.fn-item:hover {
    background: var(--hover-bg, #f0f0f0);
}

.fn-item.selected {
    color: var(--primary, #1678c2);
    background: var(--primary-light, #e8f4fd);
}

.spot-options {
    display: flex;
    align-items: center;
    color: var(--text-secondary, #666);
}

.spot-hints {
    display: flex;
    gap: 12px;
    margin-left: auto;
    font-size: 11px;
    color: var(--text-tertiary, #999);
    white-space: nowrap;
}

.spot-hints kbd {
    display: inline-block;
    min-width: 18px;
    padding: 0 4px;
    margin-right: 2px;
    border: 1px solid var(--border-light, #e8e8e8);
    border-bottom-width: 2px;
    border-radius: 4px;
    background: white;
    font-family: inherit;
    font-size: 10px;
    line-height: 15px;
    text-align: center;
    color: var(--text-secondary, #666);
    box-shadow: none;
}
</style>