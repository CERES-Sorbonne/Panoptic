<script setup lang="ts">
import { useActionStore } from '@/data/actionStore';
import { ref, watch, computed, onMounted } from 'vue'
import SelectDropdown from '../dropdowns/SelectDropdown.vue';
import { keyState } from '@/data/keyState';
import InputOptions from '../actions/InputOptions.vue';
import { SelectOption, TextQuery } from '@/data/models';
import LoadWheel from '../loading/LoadWheel.vue';
import { useSearchStore } from '@/data/stores/textSearchStore';
import { TabManager } from '@/core/TabManager';
import { CollectionManager } from '@/core/CollectionManager';

const actions = useActionStore()
const searchStore = useSearchStore()

const props = defineProps<{ tab: TabManager, size?: number, collection?: CollectionManager }>()
const emits = defineEmits(['update:query'])

// The collection this search controls — the per-view one when provided
// (FilterPanel), else the tab's primary collection.
const collection = computed(() => props.collection ?? props.tab.collection)

const inputElem = ref(null)
const isFocus = ref(false)

const defaultModes = [{ value: 'text', icon: 'search' }, { value: 'regex', icon: 'regex' }]
const modeOptions = ref<SelectOption[]>([])
const mode = ref('text')
const searchText = ref('')
const size = computed(() => props.size ?? 26)

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

function resetSearch() {
    searchText.value = ''
    emitQuery()
}

function confirmSearch() {
    emitQuery()
}

function emitQuery() {
    const newQuery: TextQuery = {
        type: mode.value,
        text: searchText.value
    }

    if (isPluginMode.value) {
        if (!actions.index[mode.value]) {
            mode.value = 'text'
            resetSearch()
            return
        }
        const ctx = actions.getContext(mode.value)
        ctx.uiInputs['text'] = searchText.value
        newQuery.ctx = ctx
    }

    setQuery(newQuery)
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
watch(mode, emitQuery)
onMounted(() => {
    updateModes()
    loadFromProps()
})

keyState.ctrlF.on(() => inputElem.value?.focus())

</script>

<template>
    <div class="cont3" :class="{ focus: isFocus }" :style="{ height: size + 'px' }">
        <div class="select-wrapper">
            <SelectDropdown :options="modeOptions" v-model="mode" placeholder="Search Mode" :no-border="true"
                :icon-only="true" :size="size * 0.6" :teleport="false" />
        </div>
        <!-- <div class="divider" :style="{ height: size * 0.6 + 'px' }" /> -->
        <div class="input-field d-flex items-align-center">
            <input class="text-input2" :style="{ height: size + 'px' }" type="text" v-model="searchText"
                :placeholder="$t('main.menu.search')" ref="inputElem" @focusin="isFocus = true"
                @focusout="isFocus = false" @blur="confirmSearch"
                @keypress.enter="t => (t.target as HTMLElement).blur()" />
            <div class="toolbar">
                <div v-if="searchStore.isLoading" :style="{ fontSize: size * 0.63 + 'px' }" style="margin-right: 2px;">
                    <LoadWheel :loading="searchStore.isLoading" />
                </div>
                <div v-if="searchText.length" :style="{ fontSize: size * 0.63 + 'px' }" style="margin-right: 2px;"
                    @click="resetSearch"><i class="bi bi-x sb" /></div>
            </div>

        </div>
        <div v-if="isPluginMode" class="options-wrapper">
            <!-- <div class="divider" :style="{ height: size * 0.6 + 'px' }" /> -->
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
}

.divider {
    width: 1px;
    background-color: var(--border-color, #ccc);
    flex-shrink: 0;
    margin: 0 2px;
}

.options-wrapper {
    display: flex;
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
    flex-grow: 1;
}

.text-input2 {
    border: none;
    background-color: transparent;
    outline: none;
    width: 100%;
}
</style>