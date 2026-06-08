<script setup lang="ts">
import { RouterView } from 'vue-router'
import '@vuepic/vue-datepicker/dist/main.css';
import './assets/theme.css';
import "@vueform/slider/themes/default.css"
import { usePanopticStore } from './data/panopticStore';
import PropertyModal from './components/modals/PropertyModal.vue';
import FolderSelectionModal from './components/modals/FolderSelectionModal.vue';
import { ModalId } from './data/models';
import ImageModal from './components/modals/ImageModal.vue';
import ImageZoomModal from './components/modals/ImageZoomModal.vue';
import { keyState } from './data/keyState';
import ExportModal2 from './components/modals/ExportModal2.vue';
import SettingsModal from './components/modals/SettingsModal.vue';
import ImportModal from './components/modals/ImportModal.vue';
import TagModal from './components/modals/TagModal.vue';
import FirstModal from './components/modals/FirstModal.vue';
import NotifModal from './components/modals/NotifModal.vue';
import { useDataStore } from './data/dataStore';
import { onMounted, onUnmounted } from 'vue';
const panoptic = usePanopticStore()
const data = useDataStore()

panoptic.init()
document.title = 'Panoptic'

const isMac = navigator.userAgent.indexOf('Mac OS X') !== -1

function setMousePos(e) {
    keyState.mouseX = e.clientX
    keyState.mouseY = e.clientY
}

function onKeyDown(ev: KeyboardEvent) {
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
        keyState.ctrlF.emit()
    }
}

function onKeyUp(ev: KeyboardEvent) {
    if (ev.key == 'Meta') keyState.cmd = false;
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
}

function onMouseMove(ev: MouseEvent) {
    keyState.ctrl = ev.ctrlKey
    keyState.alt = ev.altKey
    keyState.shift = ev.shiftKey
    keyState.cmd = ev.metaKey
    if (isMac) {
        keyState.ctrl = keyState.ctrl || keyState.alt
    }
}

onMounted(() => {
    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('keyup', onKeyUp)
    window.addEventListener('mousemove', onMouseMove)
})

onUnmounted(() => {
    window.removeEventListener('keydown', onKeyDown)
    window.removeEventListener('keyup', onKeyUp)
    window.removeEventListener('mousemove', onMouseMove)
})

</script>

<template>
    <body @mousemove="setMousePos">
        <RouterView />
    </body>
</template>

<style>
:root {

    /* Couleur de mise en exergue */
    /* --test: rgb(132, 177, 255); */
    --main: 132, 177, 255;

    /* Niveaux de gris des couleurs neutres
Ajuster pour un thème clair */
    --text-num: 255;
    --bg-num: 30;

    /* Couleurs de base */
    --text: var(--text-num), var(--text-num), var(--text-num);
    --main-color: rgb(var(--main));
    --text-color: rgba(var(--text), 0.9);
    --background-color: rgb(var(--bg-num), var(--bg-num), var(--bg-num));

    /* Variantes des couleurs neutres
Plus le coefficient à la fin est bas, plus la couleur est distincte du fond.
Les formules sont complexes pour ne pas avoir des problèmes liés à la transparence */
    --bquote-num: calc(var(--text-num) + (var(--bg-num) - var(--text-num)) * 0.18);
    --disabled-num: calc(var(--text-num) + (var(--bg-num) - var(--text-num)) * 0.47);
    --hr-num: calc(var(--text-num) + (var(--bg-num) - var(--text-num)) * 0.8);
    --li-bg-num: calc(var(--text-num) + (var(--bg-num) - var(--text-num)) * 0.95);

    --bquote: rgb(var(--bquote-num), var(--bquote-num), var(--bquote-num));
    --disabled-color: rgb(var(--disabled-num), var(--disabled-num), var(--disabled-num));
    --hr-color: rgb(var(--hr-num), var(--hr-num), var(--hr-num));
    --light-background: rgb(var(--li-bg-num), var(--li-bg-num), var(--li-bg-num));

    /* Diviseurs et contours */
    --hr: var(--border-width) solid var(--hr-color);
    --hr-main: var(--border-width) solid rgba(var(--main), 0.8);
    --border-width: 0.13rem;

    /* Code */
    --code: var(--main-color);

    /* Mesures de cartes */
    --in-card-margin: 0.6rem;
    --card-padding: 1rem;
    --card-border-radius: 0.4rem;
}

.btn-icon:hover {
    cursor: pointer;
    user-select: none;
}

/* textarea:focus, input:focus{
    outline: none !important;
} */
</style>