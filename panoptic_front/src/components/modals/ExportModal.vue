<script setup lang="ts">

import { apiExportProperties } from '@/data/api';
import { globalStore } from '@/data/store';
import * as bootstrap from 'bootstrap';
import { ref, onMounted, watch, computed, reactive } from 'vue';


const modalElem = ref(null)
let modal: bootstrap.Modal = null

const props = defineProps({
    id: { type: String, required: true }
})

const isActive = computed(() => globalStore.openModal.id == props.id)
const imagesId = computed(() => globalStore.getTab().collection.filterManager.result.images.map(i => i.id))
const activeProperties = computed(() => Object.entries(globalStore.tabs[globalStore.selectedTab].data.visibleProperties).filter(([k, v]) => v && parseInt(k) > 0).map(el => el[0]))
const useOnlyActiveImage = ref(false)
const useOnlyActiveProperties = ref(false)

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

function exportFile(){
    console.log(imagesId.value, activeProperties.value)
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