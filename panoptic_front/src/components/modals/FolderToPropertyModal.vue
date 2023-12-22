<script setup lang="ts">

import { Property, PropertyMode, PropertyType } from '@/data/models';
import * as bootstrap from 'bootstrap';
import { ref, onMounted, watch, computed, reactive } from 'vue';
import PropertyTypeDropdown from '@/components/dropdowns/PropertyTypeDropdown.vue';
import { useStore } from '@/data/store2';

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
    <div class="modal fade text-dark modal-m" role="dialog" ref="modalElem">
        <div class="modal-dialog">
            <div class="modal-content" v-if="isActive">
                <div class="modal-header m-0 p-2 ps-3 pe-3">
                    <b class="modal-title" id="exampleModalLabel">Nouvelle propriété</b>
                    <button type="button" class="btn-close" @click="hide" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    test
                </div>
                <div class="modal-footer pt-2 pb-2">
                    <button type="button" @click="hide">Anuler</button>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped></style>