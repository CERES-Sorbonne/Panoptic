<script setup lang="ts">
import { ModalId } from '@/data/models';
import { computed, onMounted, ref, watch } from 'vue';
import * as bootstrap from 'bootstrap';
import { usePanopticStore } from '@/data/panopticStore';

const panoptic = usePanopticStore()

const props = defineProps<{
    id: ModalId
    maxWidth?: number
    maxHeight?: number
    noTitle?: boolean
}>()

const emits = defineEmits(['resize', 'show', 'hide'])
defineExpose({
    hide
})

const modalElem = ref(null)
let modal: bootstrap.Modal = null

const totalHeight = ref(0)
const totalWidth = ref(0)

const active = ref(false)
const modalWidth = computed(() => totalWidth.value - 56)
const modalHeight = computed(() => totalHeight.value - 56)

const data = computed(() => panoptic.modalData)
const modalStyle = computed(() => {
    return { maxWidth: modalWidth.value + 'px', height: modalHeight.value + 'px' }
})
const bodyStyle = computed(() => {
    // return { maxWidth: modalWidth.value + 'px', height: modalHeight.value + 'px' }
    return { width: '100%', height: '100%', overflowY: 'scroll' } as any
})

function hide() {
    modal.hide()
}

function show() {
    active.value = true
    modal.show()
}

function onShow() {
    active.value = true
    emits('show')
}

function onHide() {
    active.value = false
    if (panoptic.openModalId == props.id) {
        panoptic.hideModal(props.id)
    }
    emits('hide')
}

function onWindowResize() {
    totalWidth.value = window.innerWidth
    totalHeight.value = window.innerHeight

    if (props.maxWidth && (props.maxWidth + 56) < totalWidth.value) { totalWidth.value = props.maxWidth + 56 }
    if (props.maxHeight && (props.maxHeight + 56) < totalHeight.value) { totalHeight.value = props.maxHeight + 56 }

    emits('resize', { height: totalHeight.value, width: totalWidth.value })
}

onMounted(() => {
    modal = bootstrap.Modal.getOrCreateInstance(modalElem.value)
    modalElem.value.addEventListener('hide.bs.modal', onHide)
    modalElem.value.addEventListener('show.bs.modal', onShow)
    window.addEventListener('resize', onWindowResize)
    onWindowResize()
})

watch(() => panoptic.openModalId, () => {
    if (panoptic.openModalId == props.id) {
        show()
        onWindowResize()
    }
    else if (active.value) {
        hide()
    }
})

</script>

<template>
    <div class="modal" tabindex="-1" ref="modalElem">
        <div class="modal-dialog modal-container" :style="modalStyle">
            <div class="modal-content d-flex flex-column h-100" v-if="active">
                <div class="title" v-if="!props.noTitle">
                    <div class="d-flex">
                        <div class="flex-grow-1">
                            <slot name="title"></slot>
                        </div>
                        <div class="close bi bi-x btn-icon" @click="hide"></div>
                    </div>
                </div>
                <div class="body flex-grow-1" :style="bodyStyle">
                    <slot name="content" :data="data"></slot>
                </div>
            </div>
        </div>
    </div>
</template>


<style scoped>
.modal-container {
    background-color: white;
    border-radius: 3px;
    overflow: hidden;

    border-radius: 3px !important;
    border: 2px solid var(--border-color) !important;

}

.body {
    background-color: white;
    overflow: hidden;
}

.title {
    /* border-bottom: 1px solid var(--border-color); */
    background-color: rgb(238, 238, 255);
    padding: 4px 4px;
}

.close {
    /* border-left: 1px solid var(--border-color); */
    padding: 0 6px;
}

.modal-content {
    padding: 0 !important;
    margin: 0 !important;
    overflow: hidden;
    border: none !important;
    border-radius: 0 !important;
}
</style>