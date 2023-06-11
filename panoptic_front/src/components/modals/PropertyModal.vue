<script setup lang="ts">

import { Property, PropertyType } from '@/data/models';
import { globalStore } from '@/data/store';
import * as bootstrap from 'bootstrap';
import { ref, onMounted, watch, computed, reactive } from 'vue';
import PropertyTypeDropdown from '@/components/Dropdowns/PropertyTypeDropdown.vue';
import PropertyModeDropdown from '../Dropdowns/PropertyModeDropdown.vue';


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
    resetNewProperty()
}

function hide() {
    modal.hide()
}

function show() {
    modal.show()
}

const newProperty = reactive({}) as Property
const nameError = ref('')

function resetNewProperty() {
    newProperty.name = ''
    newProperty.type = PropertyType.string
    nameError.value = ''
}

async function saveProperty() {

    if (!newProperty.name) {
        nameError.value = 'Name is Empty!'
        return
    }
    let propNames = Object.values(globalStore.properties).map(p => p.name)
    if (propNames.includes(newProperty.name)) {
        nameError.value = 'A Property with same name already exist! Please choose a new name'
        return
    }

    await globalStore.addProperty(newProperty.name, newProperty.type, newProperty.mode)

    hide()
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
    resetNewProperty()
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
                    <form @submit.prevent="saveProperty" class="d-flex flex-row">
                        <div class="me-1">
                            <PropertyModeDropdown v-model="newProperty.mode" />
                        </div>
                        <div class="me-1">
                            <input type="text" class="text-input input-lg" id="propertyName" name="propertyName"
                                v-model="newProperty.name" required>
                            <div class="invalid-feedback">
                                {{ nameError }}
                            </div>
                        </div>
                        <div class="">
                            <PropertyTypeDropdown v-model="newProperty.type" class="input-lg" />
                        </div>

                    </form>
                </div>
                <div class="modal-footer pt-2 pb-2">
                    <button type="button" @click="hide">Anuller</button>
                    <button type="button" @click="saveProperty">Confirmer</button>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped></style>