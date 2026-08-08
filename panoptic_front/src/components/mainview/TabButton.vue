<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue';
import wTT from '../tooltips/withToolTip.vue'
import { TabManager } from '@/core/TabManager';
import { useTabStore } from '@/data/tabStore';

const tabStore = useTabStore()

const newTabName = ref('')
const isHover = ref(false)
const isEdit = ref(false)
const rootElem = ref<HTMLElement>(null)
const inputElem = ref<HTMLInputElement>(null)

const props = defineProps<{
    tab: TabManager
}>()

const tabId = computed(() => props.tab.state.id)

// Bring the tab into view whenever it becomes the active tab — covers selection
// from the picker dropdown, a click, or restore on load.
watch(() => tabStore.mainTab === tabId.value, (isActive) => {
    if (!isActive) return
    nextTick(() => rootElem.value?.scrollIntoView({ behavior: 'smooth', inline: 'nearest', block: 'nearest' }))
}, { immediate: true })

function select() {
    tabStore.selectMainTab(props.tab.state.id)
}

function doubleClick() {
    if (tabStore.mainTab === props.tab.state.id) {
        setEditTab()
    }
}

function setEditTab() {
    isEdit.value = true
    newTabName.value = props.tab.state.name
    // Select the whole name so typing replaces it — the field looks like plain
    // text, so a visible selection is the only cue that it is editable.
    nextTick(() => {
        inputElem.value?.focus()
        inputElem.value?.select()
    })
}

function cancelEdit() {
    newTabName.value = props.tab.state.name
    isEdit.value = false
}

function endEdit() {
    // Escape already closed the editor (and restored the name) — a trailing
    // blur must not re-commit it.
    if (!isEdit.value) return
    if (newTabName.value.trim()) {
        props.tab.renameTab(newTabName.value)
    } else {
        newTabName.value = props.tab.state.name
    }
    isEdit.value = false
}

function focusOut() {
    endEdit()
}

async function deleteTab() {
    let ok = confirm('Are you sure to delete Tab: ' + props.tab.state.name)
    if (!ok) return
    tabStore.deleteTab(props.tab.state.id)
}

onMounted(() => {
    if (props.tab.isNew) {
        setEditTab()
    }
})
</script>

<template>
    <div ref="rootElem" class="tab-item d-flex d-row" @mouseenter="isHover = true" @mouseleave="isHover = false">
        <template v-if="!isEdit">
            <div class="tab-button" :class="(tabId == tabStore.mainTab ? ' active' : '')" @click="select"
                @dblclick="doubleClick">
                <span>{{ props.tab.state.name }}</span>
            </div>
            <span class="tab-close" :class="{ hidden: !isHover }">
                <wTT message="main.menu.delete_tab_tooltip">
                    <i @click="deleteTab" class="bi bi-x"></i>
                </wTT>
            </span>
        </template>
        <template v-else>
            <div class="tab-button editing" :class="(tabId == tabStore.mainTab ? ' active' : '')">
                <!-- The sizer is an invisible copy of the text that gives the wrapper its
                     width; the input is stretched over it. Same font as the sizer (both
                     inherit from .tab-button), so the field grows exactly with the name
                     and the caret sits where the label was. -->
                <span class="tab-name-edit">
                    <span class="tab-name-sizer">{{ newTabName }}</span>
                    <input ref="inputElem" class="tab-name-input" type="text" v-model="newTabName"
                        @keydown.enter="endEdit" @keydown.escape="cancelEdit" @focusout="focusOut" />
                </span>
            </div>
        </template>
    </div>
</template>

<style scoped>
.tab-button.active {
    background-color: var(--primary-light);
}

/* Rename field: chromeless, so editing reads as typing directly on the tab
   label rather than a box appearing inside the pill. */
.tab-name-edit {
    position: relative;
    display: inline-block;
    min-width: 1ch;
}

/* Invisible but laid out — it is what sizes the wrapper to the text. `pre`
   keeps trailing spaces so the width doesn't jump while typing them. */
.tab-name-sizer {
    visibility: hidden;
    white-space: pre;
}

.tab-name-input {
    position: absolute;
    inset: 0;
    width: 100%;
    padding: 0;
    margin: 0;
    border: none;
    outline: none;
    background: transparent;
    box-shadow: none;
    /* Match the label exactly: same font/size/weight/colour as .tab-button. */
    font: inherit;
    letter-spacing: inherit;
    color: inherit;
}

.tab-name-input::selection {
    background-color: var(--primary-light, #cfe2ff);
}
</style>

<style>
.no-border {
    border: none !important;
}

.hidden {
    visibility: hidden;
}

.lang {
    margin-left: auto;
    order: 2;
    margin-top: 0.1em;
    margin-right: 0.5em;
    font-size: 16px
}
</style>