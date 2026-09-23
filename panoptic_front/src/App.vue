<script setup lang="ts">
import { RouterView } from 'vue-router'
import { computed, watch } from 'vue';
import '@vuepic/vue-datepicker/dist/main.css';
import './assets/theme.css';
import "@vueform/slider/themes/default.css"
import { usePanopticStore } from './data/stores/panopticStore';
import { useKeyState } from './data/composables/keyState';
import { isTauri, useTauriLauncherStore } from './data/tauriLauncherStore';
import TauriLauncher from './components/tauri/TauriLauncher.vue';

const panoptic = usePanopticStore()
useKeyState()

const launcher = isTauri ? useTauriLauncherStore() : null
const backendReady = computed(() => !isTauri || launcher.phase === 'ready')

if (isTauri) {
    // sous Tauri le launcher installe/démarre le backend d'abord ;
    launcher.start()
}

const stopInit = watch(backendReady, (ready) => {
    if (!ready) return
    panoptic.init()
    stopInit()
}, { immediate: true })

document.title = 'Panoptic'

</script>

<template>
    <TauriLauncher v-if="!backendReady" />
    <RouterView v-else />
</template>