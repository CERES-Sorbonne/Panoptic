<script setup lang="ts">

import { Tab } from '@/data/models';
import { globalStore } from '@/data/store';
import { onMounted, reactive, ref } from 'vue';


function select(id: number) {
    globalStore.selectedTab = id
}

function addTab(event: any) {
    globalStore.addTab('New Tab')
}

async function deleteTab(tab: Tab) {
    if(Object.keys(globalStore.tabs).length == 1) {
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
            <div class="d-flex d-row me-2" v-for="tab in globalStore.tabs" @mouseenter="e => hover[tab.id] = true" @mouseleave="e => hover[tab.id] = false">
                <!-- <i class="btn-icon bi bi-pencil tab-icon me-2" :class="hover[tab.id] ? '' : 'hidden'" style="font-size: 9px;"></i> -->
                <button  class="tab-button" :class="(tab.id == globalStore.selectedTab ? ' active' : '')" @click="select(tab.id)"><span>{{ tab.name }}</span></button>
                <i @click="deleteTab(tab)" class="btn-icon bi bi-x tab-icon" style="font-size: 15px;" :class="hover[tab.id] ? '' : 'hidden'"></i>
            </div>
            <button class="tab-icon" @click="addTab"><span class="bi bi-plus"></span></button>
        </div>
    </nav>
</template>

<style>
.no-border{
   border: none !important;
}

.hidden {
    visibility: hidden;
}

</style>