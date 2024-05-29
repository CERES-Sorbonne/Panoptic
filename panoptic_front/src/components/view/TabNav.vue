<script setup lang="ts">
import {reactive, ref, nextTick } from 'vue';
import wTT from '../tooltips/withToolTip.vue'
import { useProjectStore } from '@/data/projectStore';
import { TabState } from '@/data/models';


const project = useProjectStore()

const editTab = ref(-1)
const newTabName = ref('')
const inputElem = ref(null)

const props = defineProps({
    reRender: Function
})


function select(id: number) {
    if (project.data.selectedTabId == id) {
        // setEditTab(id)
    }
    else {
        endEdit()
    }
    project.selectTab(id)
}

function setEditTab(id: number) {
    editTab.value = id
    newTabName.value = project.data.tabs[id].name
    nextTick(() => inputElem.value[0].focus())
}

function endEdit() {
    editTab.value = -1
    newTabName.value = ''
}

function addTab(event: any) {
    project.addTab('New Tab')
}

async function deleteTab(tab: TabState) {
    let ok = confirm('Are you sure to delete Tab: ' + tab.name)
    if(!ok) return
    await project.removeTab(tab.id)
}

const hover = reactive({}) as any
const editId = ref(-1)
const langs = ['fr', 'en']

</script>

<template>
    <nav>
        <div class="d-flex d-row" style="cursor: pointer;">
            <div class="d-flex d-row me-2" v-for="tab in project.data.tabs" @mouseenter="e => hover[tab.id] = true"
                @mouseleave="e => hover[tab.id] = false">
                <!-- <i class="btn-icon bi bi-pencil tab-icon me-2" :class="hover[tab.id] ? '' : 'hidden'" style="font-size: 9px;"></i> -->
                <template v-if="editTab != tab.id">
                    <wTT message="main.menu.rename_tab_tooltip"><i @click="setEditTab(tab.id)" class="bi bi-pencil me-1 tab-icon hover-light" :class="(hover[tab.id] && project.data.selectedTabId == tab.id)? '' : 'hidden'" style="font-size: 10px;"></i></wTT>
                    <div class="tab-button" :class="(tab.id == project.data.selectedTabId ? ' active' : '')"
                        @click="select(tab.id)">
                        <span>{{ tab.name }}</span>
                    </div>
                    <wTT message="main.menu.delete_tab_tooltip">
                        <i @click="deleteTab(tab)" class="btn-icon bi bi-x tab-icon hover-light" style="font-size: 15px;"
                            :class="hover[tab.id] ? '' : 'hidden'"></i>
                    </wTT>
                </template>
                <template v-else>
                    <div class="tab-button" :class="(tab.id == project.data.selectedTabId ? ' active' : '')">
                        <form @submit.stop.prevent="endEdit"><input @focusout="endEdit" @keydown.escape="endEdit" type="text" class="text-input" v-model="tab.name" ref="inputElem"/></form>
                    </div>
                    
                </template>
            </div>
            <wTT message="main.menu.add_tab_tooltip"><button class="tab-icon hover-light ps-1 pe-1" @click="addTab" id="add-tab-button" ><span class="bi bi-plus"></span></button></wTT>
            <div class="lang">
                <i class="bi bi-translate" style="margin-right:0.5rem"></i>
                <select v-model="$i18n.locale" @change="props.reRender()">
                    <option v-for="(lang, i) in langs" :key="`Lang${i}`" :value="lang">
                        {{ lang.toUpperCase() }}
                    </option>
                </select>
        </div>
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

.lang{
    margin-left: auto;
    order: 2;
    margin-top: 0.1em;
    margin-right: 0.5em;
    font-size:16px
}
</style>