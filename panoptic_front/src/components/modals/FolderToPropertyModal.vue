<script setup lang="ts">

import { globalStore } from '@/data/store';
import * as bootstrap from 'bootstrap';
import { ref, onMounted, watch, computed, reactive } from 'vue';
import FileExplorer from './FileExplorer.vue';

const modalElem = ref(null)
let modal: bootstrap.Modal = null

const props = defineProps({
    id: { type: String, required: true }
})

const isActive = computed(() => globalStore.openModal.id == props.id)


function onHide() {
    if (globalStore.openModal.id == props.id) {
        globalStore.hideModal()
    }
}

function hide() {
    modal.hide()
}

function show() {
    modal.show()
}

watch(() => globalStore.openModal.id, (id) => {
    if (id == props.id) {
        show()
    }
    else {
        hide()
    }
})

onMounted(() => {
    modal = bootstrap.Modal.getOrCreateInstance(modalElem.value)
    modalElem.value.addEventListener('hide.bs.modal', onHide)
})
</script>


<template>
    <div class="modal fade text-dark modal-m" role="dialog" ref="modalElem">
        <div class="modal-dialog" style="max-width: none;width: 90vw;height: 85vh">
            <div class="modal-content" v-if="isActive">
                <div class="modal-header m-0 p-2 ps-3 pe-3">
                    <b class="modal-title" id="exampleModalLabel">Choisir un dossier d'images à ajouter</b>
                    <button type="button" class="btn-close" @click="hide" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <FileExplorer />
                </div>
            </div>
        </div>
        <!-- <vue-finder id='my_vuefinder' url="http://localhost:8000/finder"></vue-finder> -->
    </div>
</template>

<style scoped></style>