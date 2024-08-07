<script setup lang="ts">
import router from '@/router';
import { ref, computed, onMounted, nextTick, onUnmounted, provide } from 'vue';
import Menu from '../components/menu/Menu.vue';

import { keyState } from '@/data/keyState';
import MainView from '@/components/view/MainView.vue';
import TabNav from '@/components/view/TabNav.vue';
import { ModalId } from '@/data/models';
import { useProjectStore } from '@/data/projectStore';
import { usePanopticStore } from '@/data/panopticStore';
import Tutorial from '@/tutorials/Tutorial.vue';
import { useDataStore } from '@/data/dataStore';

const project = useProjectStore()
const data = useDataStore()
const panoptic = usePanopticStore()

const mainViewRef = ref(null)
const navElem = ref(null)
const windowHeight = ref(window.innerHeight)
const hasHeight = ref(false)

const contentHeight = computed(() => windowHeight.value - (navElem.value?.clientHeight ?? 0))
const filteredImages = computed(() => mainViewRef.value?.filteredImages.map(i => i.id))

let isMac = navigator.userAgent.indexOf('Mac OS X') !== -1

onMounted(async () => {
    if (!panoptic.isProjectLoaded) {
        // console.log('redirect')
        router.push('/')
    }

    nextTick(() => {
        window.addEventListener('resize', onResize);
        onResize()
    })

    window.addEventListener('keydown', (ev) => {
        if (ev.key == 'Control') keyState.ctrl = true;
        if (ev.key == 'Alt') {
            if (isMac) {
                keyState.ctrl = true
            }
            keyState.alt = true;
        }
        if (ev.key == 'Shift') keyState.shift = true;
        if (ev.key == 'ArrowLeft') keyState.left = true;
        if (ev.key == 'ArrowRight') { keyState.right = true; console.log('keeeyy') }

        if (ev.key == 'Z' && keyState.ctrl) data.redo()
        if (ev.key == 'z' && keyState.ctrl) data.undo()
    })
    window.addEventListener('keyup', (ev) => {
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
        if (isMac) {
            keyState.ctrl = keyState.ctrl || keyState.alt
        }
    })
})

onUnmounted(() => {
    window.removeEventListener('resize', onResize);
})

function onResize() {
    // console.log('resize', window.innerHeight)
    windowHeight.value = window.innerHeight
    hasHeight.value = true
}

function showModal() {
    panoptic.showModal(ModalId.EXPORT, filteredImages)
}

function reRender() {
    project.rerender()
}

function redirectHome() {
    router.push('/')
}


</script>

<template>
    <Tutorial tutorial="project" /> <!---</Tutorial>v-if="mainViewRef && !mainViewRef.imageList"/>-->
    <div id="panoptic" :key="project.status.renderNb">
        <!-- <div id="dropdown-target" style="position: relative; z-index: 99; left: 0; right: 0; top:0; bottom: 0;" class="overflow-hidden"></div> -->
        <div class="d-flex flex-row m-0 p-0 overflow-hidden">
            <template v-if="project.status.loaded">
                <div>
                    <Menu @export="showModal()" />
                </div>
                <div class="w-100">
                    <div class="ms-3" ref="navElem">
                        <TabNav :re-render="reRender" />
                    </div>
                    <div class="custom-hr" v-if="hasHeight" />

                    <MainView :tab-id="project.data.selectedTabId" :height="contentHeight" ref="mainViewRef" />
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