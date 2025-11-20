<script setup lang="ts">

import * as bootstrap from 'bootstrap';
import { ref, onMounted, watch, computed, reactive } from 'vue';
import FileExplorer from './FileExplorer.vue';
import { usePanopticStore } from '@/data/panopticStore';
import { ModalId } from '@/data/models';
import { useModalStore } from '@/data/modalStore';

const modalStore = useModalStore()
const panoptic = usePanopticStore()
const mode = computed(() => modalStore.getData(props.id).mode)
const data = computed(() => modalStore.getData(props.id))

const modalElem = ref(null)
let modal: bootstrap.Modal = null

const props = defineProps<{id: ModalId}>()

const isActive = computed(() => modalStore.isOpen(props.id))

function onHide() {
    if (data.value?.callback) {
        data.value.callback(undefined)
    }
    if (panoptic.openModalId == props.id) {
        panoptic.hideModal(ModalId.FOLDERSELECTION)
    }
}

function hide() {
    modal.hide()
}

function show() {
    console.log('show file explorer', isActive.value)
    modal.show()
}

function select(path) {
    if (data.value?.callback) {
        data.value.callback(path)
        if (data.value.callback) {
            data.value.callback = undefined

        }
    }
    hide()
}

watch(() => panoptic.openModalId, (id) => {
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

modalStore.registerModal(props.id, 2)

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