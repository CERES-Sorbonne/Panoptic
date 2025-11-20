<script setup lang="ts">
import router from '@/router';
import { ref, computed, onMounted, nextTick, onUnmounted, provide } from 'vue';
import Menu from '../components/menu/Menu.vue';

import { keyState } from '@/data/keyState';
import MainView from '@/components/mainview/MainView.vue';
import TabNav from '@/components/mainview/TabNav.vue';
import { ModalId } from '@/data/models';
import { useProjectStore } from '@/data/projectStore';
import { usePanopticStore } from '@/data/panopticStore';
import Tutorial from '@/tutorials/Tutorial.vue';
import { useDataStore } from '@/data/dataStore';
import TabContainer from '@/components/TabContainer.vue';
import { useTabStore } from '@/data/tabStore';
import DataLoad from '@/components/loading/DataLoad.vue';

let x = 0

const project = useProjectStore()
const data = useDataStore()
const panoptic = usePanopticStore()
const tabStore = useTabStore()

const mainViewRef = ref(null)
const navElem = ref(null)
const windowHeight = ref(window.innerHeight)
const hasHeight = ref(false)
const show = ref(true)

const filterOpen = ref(true)

const contentHeight = computed(() => windowHeight.value - (navElem.value?.clientHeight ?? 0))
const filteredImages = computed(() => mainViewRef.value?.filteredImages.map(i => i.id))

let isMac = navigator.userAgent.indexOf('Mac OS X') !== -1

async function rerender() {
    show.value = false
    await nextTick()
    show.value = true
}

onMounted(async () => {
    if (!panoptic.isProjectLoaded) {
        router.push('/')
        return
    }

    project.init()

    nextTick(() => {
        window.addEventListener('resize', onResize);
        onResize()
    })

    window.addEventListener('keydown', (ev) => {
        if (ev.key == 'Meta') keyState.cmd = true;
        if (ev.key == 'Control') keyState.ctrl = true;
        if (ev.key == 'Alt') {
            if (isMac) {
                keyState.ctrl = true
            }
            keyState.alt = true;
        }
        if (ev.key == 'Shift') keyState.shift = true;
        if (ev.key == 'ArrowLeft') keyState.left = true;
        if (ev.key == 'ArrowRight') { keyState.right = true; }

        if (ev.key == 'Z' && keyState.ctrl) data.redo()
        if (ev.key == 'z' && keyState.ctrl) data.undo()

        if (ev.key == 'f' && (keyState.ctrl || keyState.cmd)) {
            ev.preventDefault()
            // ev.stopImmediatePropagation()
            keyState.ctrlF.emit()
        }
    })
    window.addEventListener('keyup', (ev) => {
        if (ev.key == 'Meta') keyState.cmd = false; //
        if (ev.key == 'Control') keyState.ctrl = false;
        if (ev.key == 'Alt') {
            if (isMac) {
                keyState.ctrl = false
            }
            keyState.alt = false;
        }
        if (ev.key == 'Shift') keyState.shift = false;
        if (ev.key == 'ArrowLeft') keyState.left = false;
        if (ev.key == 'ArrowRight') keyState.right = false;
    })
    window.addEventListener('mousemove', (ev) => {
        keyState.ctrl = ev.ctrlKey
        keyState.alt = ev.altKey
        keyState.shift = ev.shiftKey
        keyState.cmd = ev.metaKey
        if (isMac) {
            keyState.ctrl = keyState.ctrl || keyState.alt
        }
    })
})

onUnmounted(() => {
    window.removeEventListener('resize', onResize);
    useProjectStore().clear()
})

function onResize() {
    // console.log('resize', window.innerHeight)
    windowHeight.value = window.innerHeight
    hasHeight.value = true
}

function showModal() {
    panoptic.showModal(ModalId.EXPORT, filteredImages)
}

function redirectHome() {
    router.push('/')
}

function updateWidth() {
    if (mainViewRef.value) {
        mainViewRef.value.updateScrollerWidth()
    }
}

</script>

<template>
    <div v-if="show">
        <Tutorial v-if="mainViewRef && !mainViewRef.imageList" tutorial="project" />
        <!---</Tutorial>v-if="mainViewRef && !mainViewRef.imageList"/>-->
        <div id="panoptic">
            <!-- <div id="dropdown-target" style="position: relative; z-index: 99; left: 0; right: 0; top:0; bottom: 0;" class="overflow-hidden"></div> -->
            <div class="d-flex flex-row m-0 p-0 overflow-hidden">
                <div v-if="!data.isLoaded" class="d-flex flex-column w-100" :style="{ height: windowHeight + 'px' }">
                    <DataLoad class="flex-grow-1" />
                </div>
                <template v-else-if="data.isLoaded">
                    <div>
                        <Menu @export="showModal()" @toggle="updateWidth" />
                    </div>
                    <div class="w-100">
                        <div class="ms-1" ref="navElem">
                            <TabNav :re-render="rerender" :filterOpen="filterOpen"
                                @update:filterOpen="v => filterOpen = v" />
                        </div>
                        <div class="custom-hr" v-if="hasHeight" />
                        <TabContainer :id="tabStore.mainTab">
                            <template #default="{ tab }">
                                <MainView :tab="tab" :height="contentHeight" ref="mainViewRef"
                                    :filter-open="filterOpen" />
                            </template>
                        </TabContainer>
                    </div>

                </template>
                <div v-else-if="!panoptic.isProjectLoaded" class="loading">
                    <div class="text-center">
                        <div>{{ $t('main.status.no_project') }}</div>
                        <div class="bi bi-house p-3" @click="redirectHome" style="font-size: 50px; cursor: pointer;">
                        </div>
                    </div>
                </div>
                <div v-else class="loading">
                    <i class="spinner-border" role="status"></i>
                    <span class="ms-1">Loading...</span>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.loading {
    width: 100%;
    height: 100vh;
    display: flex;
    justify-content: center;
    align-items: center;
}
</style>