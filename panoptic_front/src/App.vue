<script setup lang="ts">
import { RouterView } from 'vue-router'
import '@vuepic/vue-datepicker/dist/main.css';
import './assets/main.css';
import { usePanopticStore } from './data/panopticStore';
import ImageModal from './components/modals/ImageModal.vue';
import PropertyModal from './components/modals/PropertyModal.vue';
import FolderSelectionModal from './components/modals/FolderSelectionModal.vue';
import ExportModal from './components/modals/ExportModal.vue';
import { ModalId } from './data/models';
import Modal from './components/modals/Modal.vue';
import ImageModal2 from './components/modals/ImageModal2.vue';

const panoptic = usePanopticStore()
panoptic.init()
document.title = 'Panoptic'
</script>

<template>
  <body>
    <RouterView />
    <!-- <ImageModal :id="ModalId.IMAGE" /> -->
    <PropertyModal :id="ModalId.PROPERTY" />
    <FolderSelectionModal :id="ModalId.FOLDERSELECTION" />
    <ExportModal :id="ModalId.EXPORT" />
    <ImageModal2 />
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