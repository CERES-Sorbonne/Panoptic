<script setup lang="ts">

import { apiExportProperties } from '@/data/api';
import { usePanopticStore } from '@/data/panopticStore';
import { useProjectStore } from '@/data/projectStore';
import * as bootstrap from 'bootstrap';
import { ref, onMounted, watch, computed, reactive } from 'vue';

const panoptic = usePanopticStore()
const store = useProjectStore()
const tabManager = store.getTabManager()

const modalElem = ref(null)
let modal: bootstrap.Modal = null

const props = defineProps({
    id: { type: String, required: true }
})

const isActive = computed(() => panoptic.openModal.id == props.id)
const imagesId = computed(() => tabManager.collection.filterManager.result.images.map(i => i.id))
const activeProperties = computed(() => tabManager.getVisibleProperties().filter(p => p.id >= 0))
const useOnlyActiveImage = ref(false)
const useOnlyActiveProperties = ref(false)

function onHide() {
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

function exportFile(){
    let images
    let properties
    if(useOnlyActiveImage.value){
        images = imagesId.value
    }
    if(useOnlyActiveProperties.value){
        properties = activeProperties.value
    }
    apiExportProperties(images, properties)
}

</script>


<template>
    <div class="modal fade text-dark modal-m" role="dialog" ref="modalElem">
        <div class="modal-dialog">
            <div class="modal-content" v-if="isActive">
                <div class="modal-header m-0 p-2 ps-3 pe-3">
                    <b class="modal-title" id="exampleModalLabel">{{$t("modals.export.title")}}</b>
                    <button type="button" class="btn-close" @click="hide" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <div class="form-check">
                        <input class="form-check-input" type="checkbox" value="useOnlyActiveImage" id="checkImages" v-model="useOnlyActiveImage">
                        <label class="form-check-label" for="flexCheckDefault">
                            {{$t("modals.export.images")}}
                        </label>    
                    </div>
                    <div class="form-check">
                        <input class="form-check-input" type="checkbox" value="useOnlyActiveProperties" id="checkProperties" v-model="useOnlyActiveProperties">
                        <label class="form-check-label" for="flexCheckDefault">
                            {{$t("modals.export.properties")}}
                        </label>
                    </div>
                </div>
                <div class="modal-footer pt-2 pb-2">
                    <button type="button" @click="exportFile">{{$t("modals.export.export")}}</button>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped></style>