<script setup lang="ts">

import { Tab } from '@/data/models';
import { globalStore } from '@/data/store';
import { onMounted, reactive, ref, nextTick, unref } from 'vue';

const editTab = ref(-1)
const newTabName = ref('')
const inputElem = ref(null)

function select(id: number) {
    if (globalStore.selectedTab == id) {
        setEditTab(id)
    }
    else {
        endEdit()
    }
    globalStore.selectedTab = id
}

function setEditTab(id: number) {
    editTab.value = id
    newTabName.value = globalStore.tabs[id].name
    nextTick(() => inputElem.value[0].focus())
}

function endEdit() {
    editTab.value = -1
    newTabName.value = ''
}

function addTab(event: any) {
    globalStore.addTab('New Tab')
}

async function deleteTab(tab: Tab) {
    if (Object.keys(globalStore.tabs).length == 1) {
        await globalStore.addTab('Tab1')
    }
    await globalStore.removeTab(tab.id)
}

const hover = reactive({}) as any
const editId = ref(-1)

</script>

<template>
    <nav>
        <div class="d-flex d-row" style="cursor: pointer;">
            <div class="d-flex d-row me-2" v-for="tab in globalStore.tabs" @mouseenter="e => hover[tab.id] = true"
                @mouseleave="e => hover[tab.id] = false">
                <!-- <i class="btn-icon bi bi-pencil tab-icon me-2" :class="hover[tab.id] ? '' : 'hidden'" style="font-size: 9px;"></i> -->
                <template v-if="editTab != tab.id">
                    <div class="tab-button" :class="(tab.id == globalStore.selectedTab ? ' active' : '')"
                        @click="select(tab.id)"><span>{{ tab.name }}</span></div>
                    <i @click="deleteTab(tab)" class="btn-icon bi bi-x tab-icon" style="font-size: 15px;"
                        :class="hover[tab.id] ? '' : 'hidden'"></i>
                </template>
                <template v-else>
                    <div class="tab-button" :class="(tab.id == globalStore.selectedTab ? ' active' : '')">
                        <form @submit.stop.prevent="endEdit"><input @focusout="endEdit" @keydown.escape="endEdit" type="text" class="text-input" v-model="tab.name" ref="inputElem"/></form>
                    </div>
                    
                </template>
            </div>
            <button class="tab-icon" @click="addTab"><span class="bi bi-plus"></span></button>
        </div>
    </nav>
</template>

<style>
.no-border {
    border: none !important;
}

.hidden {
    visibility: hidden;
}
</style>