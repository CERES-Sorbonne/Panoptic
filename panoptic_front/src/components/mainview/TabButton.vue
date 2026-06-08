<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue';
import wTT from '../tooltips/withToolTip.vue'
import { TabManager } from '@/core/TabManager';
import { useTabStore } from '@/data/tabStore';
import TextInput from '../inputs/TextInput.vue'

const tabStore = useTabStore()

const newTabName = ref('')
const isHover = ref(false)
const isEdit = ref(false)
const rootElem = ref<HTMLElement>(null)

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
}

function endEdit() {
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
            <div class="tab-button" :class="(tabId == tabStore.mainTab ? ' active' : '')" @focusout="focusOut">
                <TextInput v-model="newTabName" :focus="true" @enter="endEdit" @keydown.escape="focusOut" />
            </div>

        </template>
    </div>
</template>

<style scoped>
.tab-button.active {
    background-color: var(--primary-light);
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