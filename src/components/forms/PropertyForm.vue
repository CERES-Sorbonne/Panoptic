<script setup lang="ts">

import * as models from '@/data/models'
import { reactive, onMounted, ref } from 'vue';
import * as boostrap from 'bootstrap'
import { globalStore } from '@/data/store';
import { apiAddProperty } from '@/data/api';

const props = defineProps({
    id: { type: String, required: true }
})

const newProperty = <models.Property>reactive({})
const nameError = ref('')

function resetNewProperty() {
    newProperty.name = ''
    newProperty.type = models.PropertyType.string
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

    let elem = document.getElementById(props.id)
    let modal = boostrap.Modal.getInstance(elem)
    modal.hide()
}

onMounted(() => {
    let elem = document.getElementById(props.id)
    elem.addEventListener('hide.bs.modal', resetNewProperty)

    resetNewProperty()
})

</script>

<template>
    <div class="modal fade text-dark " :id="props.id" tabindex="-1" aria-labelledby="addPropertyModal" aria-hidden="true">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title" id="exampleModalLabel">Add Property</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
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
                                <option value="">Choose...</option>
                                <option value="string">string</option>
                                <option value="number">number</option>
                                <option value="tag">tag</option>
                                <option value="multi_tags">multi_tags</option>
                                <option value="image_link">image_link</option>
                                <option value="url">url</option>
                                <option value="date">date</option>
                                <option value="path">path</option>
                                <option value="color">color</option>
                                <option value="checkbox">checkbox</option>
                            </select>
                        </div>
                    </form>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                    <button type="button" class="btn btn-primary" @click="saveProperty">Save changes</button>
                </div>
            </div>
        </div>
    </div>
</template>