<script setup lang="ts">

import { ref, computed, onMounted, nextTick, onUnmounted } from 'vue';
import Menu from '../components/menu/Menu.vue';
import { Modals } from '@/data/models';
import ImageModal from '@/components/modals/ImageModal.vue';
import PropertyModal from '@/components/modals/PropertyModal.vue';
import { globalStore } from '@/data/store';
import ExportModal from '@/components/modals/ExportModal.vue';
import { keyState } from '@/data/keyState';
import FolderToPropertyModal from '@/components/modals/FolderToPropertyModal.vue';
import MainView from '@/components/view/MainView.vue';
import TabNav from '@/components/view/TabNav.vue';


const mainViewRef = ref(null)
const navElem = ref(null)
const windowHeight = ref(400)

const contentHeight = computed(() => windowHeight.value - (navElem.value?.clientHeight ?? 0))
const filteredImages = computed(() => mainViewRef.value?.filteredImages.map(i => i.id))

onMounted(() => {
    nextTick(() => {
        window.addEventListener('resize', onResize);
        onResize()
    })

    window.addEventListener('keydown', (ev) => {
        if(ev.key == 'Control') keyState.ctrl = true;
        if(ev.key == 'Alt') keyState.alt = true;
        if(ev.key == 'Shift') keyState.shift = true;
    })
    window.addEventListener('keyup', (ev) => {
        if(ev.key == 'Control') keyState.ctrl = false;
        if(ev.key == 'Alt') keyState.alt = false;
        if(ev.key == 'Shift') keyState.shift = false;
    })
    window.addEventListener('mousemove', (ev) => {
        keyState.ctrl = ev.ctrlKey
        keyState.alt = ev.altKey
        keyState.shift = ev.shiftKey
    })
})

onUnmounted(() => {
    window.removeEventListener('resize', onResize);
})

function onResize() {
    windowHeight.value = window.innerHeight
}

function showModal(){
    globalStore.showModal(Modals.EXPORT, filteredImages)
}

let panopticKey = ref(0)
function reRender(){
    panopticKey.value += 1
}
</script>

<template>
    <div id="panoptic" :key="panopticKey">
        <!-- <div id="dropdown-target" style="position: relative; z-index: 99; left: 0; right: 0; top:0; bottom: 0;" class="overflow-hidden"></div> -->
        <div class="d-flex flex-row m-0 p-0 overflow-hidden">
            <div v-if="globalStore.isLoaded">
                <Menu @export="showModal()"/>
            </div>
            <div class="w-100" v-if="globalStore.isLoaded">
                <div class="ms-3" ref="navElem">
                    <TabNav :re-render="reRender"/>
                </div>
                <div class="custom-hr" />
                <MainView :tab="globalStore.tabs[globalStore.selectedTab]" :height="contentHeight"
                    v-if="globalStore.isLoaded && globalStore.tagTrees" ref="mainViewRef"/>
            </div>
            <div v-else class="loading">
                <i class="spinner-border" role="status"></i>
                <span class="ms-1">Loading...</span>
            </div>
        </div>
        <ImageModal :id="Modals.IMAGE" />
        <PropertyModal :id="Modals.PROPERTY" />
        <FolderToPropertyModal :id="Modals.FOLDERTOPROP" />
        <ExportModal :id="Modals.EXPORT"/>

        
    </div>
    <!-- <div class="above bg-info">lalala</div>
                <div class="above2 bg-warning">lalala</div> -->
</template>

<style scoped>
.above {
    position: absolute;
    top: 500px;
    left: 500px;
    z-index: 200;
}

.above2 {
    position: absolute;
    top: 500px;
    left: 500px;
}

.loading {
    width: 100%;
    height: 100vh;
    display: flex;
    justify-content: center;
    align-items: center;
}
</style>