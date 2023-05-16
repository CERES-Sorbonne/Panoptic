<script setup lang="ts">

import { Property, PropertyType } from '@/data/models';
import { globalStore } from '@/data/store';
import * as bootstrap from 'bootstrap';
import { ref, onMounted, watch, computed, reactive } from 'vue';


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

const newProperty = <Property>reactive({})
const nameError = ref('')

function resetNewProperty() {
    newProperty.name = ''
    newProperty.type = PropertyType.string
    nameError.value = ''
}

async function saveProperty() {

    if(!newProperty.name) {
        nameError.value = 'Name is Empty!'
        return
    }
    let propNames = Object.values(globalStore.properties).map(p => p.name)
    if(propNames.includes(newProperty.name)) {
        nameError.value = 'A Property with same name already exist! Please choose a new name'
        return
    }

    await globalStore.addProperty(newProperty.name, newProperty.type)

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
    <div class="modal fade text-dark" role="dialog" ref="modalElem">
        <div class="modal-dialog">
            <div class="modal-content" v-if="isActive">
                <div class="modal-header">
                    <h5 class="modal-title" id="exampleModalLabel">Add Property</h5>
                    <button type="button" class="btn-close" @click="hide" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <form @submit.prevent="saveProperty">
                        <div class="mb-3">
                            <label for="propertyName" class="form-label">Property Name</label>
                            <input type="text" :class="'form-control '  + (nameError ? 'is-invalid' : '')" id="propertyName" name="propertyName"
                                v-model="newProperty.name" required>
                            <div class="invalid-feedback">
                                {{ nameError }}
                            </div>
                        </div>
                        <div class="mb-3">
                            <label for="propertyType" class="form-label">Property Type</label>
                            <select class="form-select" id="propertyType" name="propertyType" v-model="newProperty.type"
                                required>
                                <option v-for="ptype in globalStore.settings.propertyTypes" :value="ptype" >{{ ptype }}</option>
                            </select>
                        </div>
                    </form>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" @click="hide">Close</button>
                    <button type="button" class="btn btn-primary" @click="saveProperty">Save changes</button>
                </div>
            </div>
        </div>
    </div>
</template>