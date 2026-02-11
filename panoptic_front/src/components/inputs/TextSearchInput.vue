<script setup lang="ts">
import { useActionStore } from '@/data/actionStore';
import { ref, watch, computed, onMounted } from 'vue'
import SelectDropdown, { SelectOption } from '../dropdowns/SelectDropdown.vue';
import { keyState } from '@/data/keyState';
import InputOptions from '../actions/InputOptions.vue';
import { TextQuery } from '@/data/models';
import LoadWheel from '../loading/LoadWheel.vue';
import { useSearchStore } from '@/data/stores/textSearchStore';
import { FilterManager } from '@/core/FilterManager';
import { TabManager } from '@/core/TabManager';

const actions = useActionStore()
const searchStore = useSearchStore()

const props = defineProps<{ tab: TabManager, size?: number }>()
const emits = defineEmits(['update:query'])

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
    if (!props.tab.collection.filterManager.state.query) return
    mode.value = props.tab.collection.filterManager.state.query.type || 'text'
    searchText.value = props.tab.collection.filterManager.state.query.text || ''
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

async function setQuery(query) {
    if(areQueryEquals(query, props.tab.collection.filterManager.state.query)) return
    searchStore.setLoading(true)
    props.tab.collection.filterManager.setQuery(query)
    await props.tab.collection.filterManager.update(true)
    props.tab.saveState()
    searchStore.setLoading(false)

}

function areQueryEquals(query1: TextQuery, query2: TextQuery) {
    if(query1.type != query2.type) return false
    if(query1.text != query2.text) return false
    if(JSON.stringify(query1.ctx.uiInputs) !== JSON.stringify(query2.ctx.uiInputs)) return false
    return true
}

updateModes()
watch(() => props.tab.collection.filterManager.state.query, loadFromProps, { deep: true })
watch(() => actions.textSearchFunctions, updateModes)
watch(mode, emitQuery)
onMounted(() => {
    updateModes()
    loadFromProps()
})

keyState.ctrlF.on(() => inputElem.value?.focus())

</script>

<template>
    <div class="cont3">
        <div class="select-wrapper">
            <SelectDropdown :options="modeOptions" v-model="mode" placeholder="Search Mode" class="bg-white"
                :size="size * 0.6" :teleport="false" />
        </div>
        <div class="input-field d-flex items-align-center" :class="{ focus: isFocus }" :style="{ height: size + 'px' }">
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
        <div v-if="isPluginMode">
            <InputOptions :function-id="mode" :size="props.size * 0.6" :style="{ fontSize: size * 0.56 + 'px' }"
                :hide-text="true" @changed="emitQuery" />
        </div>
    </div>
</template>

<style scoped>
.cont3 {
    display: flex;
    gap: 4px;
    align-items: center;
    border-radius: 3px;
    /* overflow: hidden; */
}

.toolbar {
    display: flex;
    position: absolute;
    right: 0px;
    /* top: 0px; */
}

.input-field {
    border: 1px solid var(--border-color, #ccc);
    background-color: var(--grey, #f8f8f8);
    border-radius: 3px;
    transition: border-color 0.2s, box-shadow 0.2s;
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

.input-field:hover {
    border-color: #999;
}

.input-field.focus {
    border-color: var(--blue);
}
</style>