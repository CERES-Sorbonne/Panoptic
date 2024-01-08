<script setup lang="ts">

import * as bootstrap from 'bootstrap';
import { ref, onMounted, watch, computed, reactive } from 'vue';
import FileExplorer from './FileExplorer.vue';
import { usePanopticStore } from '@/data/panopticStore';

const panoptic = usePanopticStore()
const mode = computed(() => panoptic.openModal.data.mode)

const modalElem = ref(null)
let modal: bootstrap.Modal = null

const props = defineProps({
    id: { type: String, required: true },
})

const isActive = computed(() => panoptic.openModal.id == props.id)

function onHide() {
    if (panoptic.openModal.data?.callback) {
        panoptic.openModal.data.callback(undefined)
    }
    if (panoptic.openModal.id == props.id) {
        panoptic.hideModal()
    }
}

function hide() {
    modal.hide()
}

function show() {
    modal.show()
}

function select(path) {
    if (panoptic.openModal.data?.callback) {
        panoptic.openModal.data.callback(path)
        if (panoptic.openModal.data.callback) {
            panoptic.openModal.data.callback = undefined

        }
    }
    hide()
}

watch(() => panoptic.openModal.id, (id) => {
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
            <div class="modal-content overflow-hidden" v-if="isActive">
                <div class="modal-header m-0 p-2 ps-3 pe-3" style="z-index: 3; background-color: white;">
                    <b class="modal-title" id="exampleModalLabel">{{ $t('modals.fs.' + mode) }}</b>
                    <button type="button" class="btn-close" @click="hide" aria-label="Close"></button>
                </div>
                <div class="">
                    <FileExplorer @select="select" :mode="mode"/>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped></style>