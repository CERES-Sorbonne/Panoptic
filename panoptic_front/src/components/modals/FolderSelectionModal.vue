<script setup lang="ts">

import * as bootstrap from 'bootstrap';
import { ref, onMounted, watch, computed, reactive } from 'vue';
import FileExplorer from './FileExplorer.vue';
import { useStore } from '@/data/store';

const store = useStore()

const modalElem = ref(null)
let modal: bootstrap.Modal = null

const props = defineProps({
    id: { type: String, required: true }
})

const isActive = computed(() => store.openModal.id == props.id)


function onHide() {
    if (store.openModal.id == props.id) {
        store.hideModal()
    }
}

function hide() {
    modal.hide()
}

function show() {
    modal.show()
}

watch(() => store.openModal.id, (id) => {
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
    <div class="modal fade text-dark modal-xl" role="dialog" ref="modalElem">
        <div class="modal-dialog">
            <div class="modal-content" v-if="isActive">
                <div class="modal-header m-0 p-2 ps-3 pe-3">
                    <b class="modal-title" id="exampleModalLabel">{{$t('modals.add_folder.title')}}</b>
                    <button type="button" class="btn-close" @click="hide" aria-label="Close"></button>
                </div>
                <div class="modal-body m-0 p-0 overflow-hidden">
                    <FileExplorer />
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped></style>