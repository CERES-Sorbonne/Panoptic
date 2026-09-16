<script setup lang="ts">
import { RouterView } from 'vue-router'
import '@vuepic/vue-datepicker/dist/main.css';
import './assets/theme.css';
import "@vueform/slider/themes/default.css"
import { usePanopticStore } from './data/stores/panopticStore';
import { useKeyState } from './data/composables/keyState';

const panoptic = usePanopticStore()
useKeyState()

panoptic.init()
document.title = 'Panoptic'

</script>

<template>
    <RouterView />
</template>
