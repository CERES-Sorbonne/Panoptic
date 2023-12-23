<script setup lang="ts">

import * as bootstrap from 'bootstrap';
import { ref, onMounted, watch, computed, reactive } from 'vue';
import FileExplorer from './FileExplorer.vue';
import { useStore } from '@/data/store';
import Resizable from '../Resizable.vue';

const store = useStore()

const modalElem = ref(null)
const explorerWidth = ref(0)
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


function log(e) {
    explorerWidth.value = e
}

</script>


<template>
    <div class="modal fade text-dark modal-xl" role="dialog" ref="modalElem">
        <div class="modal-dialog">
            <div class="modal-content overflow-hidden" v-if="isActive">
                <div class="modal-header m-0 p-2 ps-3 pe-3" style="z-index: 3; background-color: white;">
                    <b class="modal-title" id="exampleModalLabel">{{ $t('modals.add_folder.title') }}</b>
                    <button type="button" class="btn-close" @click="hide" aria-label="Close"></button>
                </div>
                <!-- <Resizable @resize="log"> -->
                <!-- <FileExplorer :width="explorerWidth"/> -->
                <!-- </Resizable> -->
                <div class="">
                    <FileExplorer />
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped></style>