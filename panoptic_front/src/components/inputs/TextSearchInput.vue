<script setup lang="ts">
import { useActionStore } from '@/data/actionStore';
import { ref, watch, computed, onMounted } from 'vue'
import SelectDropdown, { SelectOption } from '../dropdowns/SelectDropdown.vue';
import { keyState } from '@/data/keyState';
import InputOptions from '../actions/InputOptions.vue';
import { TextQuery } from '@/data/models';

const actions = useActionStore()

const props = defineProps<{query: TextQuery, size?: number}>()
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
    if (!props.query) return
    mode.value = props.query.type || 'text'
    searchText.value = props.query.text || ''
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
        if(!actions.index[mode.value]) {
            mode.value = 'text'
            resetSearch()
            return
        }
        const ctx = actions.getContext(mode.value)
        ctx.uiInputs['text'] = searchText.value
        newQuery.ctx = ctx
    }

    emits('update:query', newQuery)
}

updateModes()
watch(() => props.query, loadFromProps, { deep: true })
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
            <SelectDropdown :options="modeOptions" v-model="mode" placeholder="Search Mode" class="bg-white" :size="size*0.6" />
        </div>
        <div class="input-field d-flex items-align-center" :class="{ focus: isFocus }" :style="{height: size+'px'}">
            <input class="text-input2" :style="{height: size+'px'}"  type="text" v-model="searchText" :placeholder="$t('main.menu.search')"
                ref="inputElem" @focusin="isFocus = true" @focusout="isFocus = false" @blur="confirmSearch" @keypress.enter="t => (t.target as HTMLElement).blur()"/>
            <div v-if="searchText.length" :style="{fontSize: size*0.63+'px'}" style="margin-right: 2px;" @click="resetSearch"><i class="bi bi-x sb" /></div>
        </div>
        <div v-if="isPluginMode">
            <InputOptions :function-id="mode" :size="props.size * 0.6 " :style="{fontSize: size*0.56+'px'}" :hide-text="true" @changed="emitQuery"/>
        </div>
    </div>
</template>

<style scoped>
.cont3 {
    display: flex;
    gap: 4px;
    align-items: center;
    border-radius: 3px;
    overflow: hidden;
}

.input-field {
    border: 1px solid var(--border-color, #ccc);
    background-color: var(--grey, #f8f8f8);
    border-radius: 3px;
    transition: border-color 0.2s, box-shadow 0.2s;
    padding: 0;

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