<script setup lang="ts">
// One tab in the tab bar. Click selects the tab, double click on the active
// tab renames it, and the x button deletes it.
import { ref, computed, onMounted, watch, nextTick } from 'vue';
import wTT from '../tooltips/withToolTip.vue'
import { TabManager } from '@/core/TabManager';
import { useTabStore } from '@/data/stores/tabStore';

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

// When this tab becomes active, scroll the tab bar so the tab is visible.
// This works for every way a tab gets selected (click, dropdown, page load).
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
    // Wait for the input to render, then select the whole name.
    // Typing then replaces the name, and the highlight shows the field is editable.
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
    // Escape closes the editor first, then the input loses focus and calls this
    // again. Stop here so a cancelled edit does not call renameTab.
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
                <!-- The sizer is a hidden copy of the text. It sets the width of the
                     wrapper, and the input is placed on top of it. Both use the font of
                     .tab-button, so the input grows with the name and the text does not move. -->
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

/* Rename field. The tab button draws the border and background of the field
   (see .tab-button.editing in TabPanel.vue), so the input has no box of its own. */
.tab-name-edit {
    position: relative;
    display: inline-block;
    min-width: 1ch;
}

/* Not visible, but it still takes space, so it gives the wrapper its width.
   `pre` keeps spaces at the end, so the width grows when the user types a space. */
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
    /* Same font and colour as the tab label. */
    font: inherit;
    letter-spacing: inherit;
    color: inherit;
    caret-color: var(--primary);
    cursor: text;
}

.tab-name-input::selection {
    background-color: var(--primary);
    color: var(--text-inverse);
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