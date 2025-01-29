<script setup lang="ts">
import { ref, nextTick, computed, onMounted } from 'vue';
import wTT from '../tooltips/withToolTip.vue'
import { TabManager } from '@/core/TabManager';
import { useTabStore } from '@/data/tabStore';

const tabStore = useTabStore()

const newTabName = ref('')
const inputElem = ref(null)
const isHover = ref(false)
const isEdit = ref(false)

const props = defineProps<{
    tab: TabManager
}>()

const tabId = computed(() => props.tab.state.id)

function select() {
    tabStore.selectMainTab(props.tab.state.id)
}

function setEditTab() {
    isEdit.value = true
    newTabName.value = props.tab.state.name
    nextTick(() => inputElem.value.focus())
}

function endEdit() {
    isEdit.value = false
    newTabName.value = ''
}

async function deleteTab() {
    let ok = confirm('Are you sure to delete Tab: ' + props.tab.state.name)
    if (!ok) return
    tabStore.deleteTab(props.tab.state.id)
}

onMounted(() => {
    if(props.tab.isNew) {
        setEditTab()
    }
})
</script>

<template>
    <div class="d-flex d-row me-2" @mouseenter="isHover = true"
        @mouseleave="isHover = false">
        <!-- <i class="btn-icon bi bi-pencil tab-icon me-2" :class="hover[tab.id] ? '' : 'hidden'" style="font-size: 9px;"></i> -->
        <template v-if="!isEdit">
            <wTT message="main.menu.rename_tab_tooltip"><i @click="setEditTab"
                    class="bi bi-pencil me-1 tab-icon hover-light"
                    :class="(isHover && tabStore.mainTab == tabId) ? '' : 'hidden'"
                    style="font-size: 10px;"></i></wTT>
            <div class="tab-button" :class="(tabId == tabStore.mainTab ? ' active' : '')"
                @click="select">
                <span>{{ props.tab.state.name }}</span>
            </div>
            <wTT message="main.menu.delete_tab_tooltip">
                <i @click="deleteTab" class="btn-icon bi bi-x tab-icon hover-light" style="font-size: 15px;"
                    :class="isHover ? '' : 'hidden'"></i>
            </wTT>
        </template>
        <template v-else>
            <div class="tab-button" :class="(tabId == tabStore.mainTab ? ' active' : '')">
                <form @submit.stop.prevent="endEdit"><input @focusout="endEdit" @keydown.escape="endEdit" type="text"
                        class="text-input" v-model="props.tab.state.name" ref="inputElem" /></form>
            </div>

        </template>
    </div>
</template>

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