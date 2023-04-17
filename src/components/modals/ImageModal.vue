<script setup lang="ts">
import { Image, Modals, Property, PropertyRef, PropertyType } from '@/data/models';
import { globalStore } from '@/data/store';
import * as bootstrap from 'bootstrap';
import { ref, onMounted, watch, computed } from 'vue';
import PropertyInput from '../inputs/PropertyInput.vue';
import TagInput from '../inputs/TagInput.vue';

const modalElem = ref(null)
let modal: bootstrap.Modal = null

const props = defineProps({
    id: { type: String, required: true }
})

const image = computed(() => globalStore.openModal.data as Image)
const isActive = computed(() => globalStore.openModal.id == props.id)

function hasProperty(propertyId: number) {
    return image.value.properties[propertyId] && image.value.properties[propertyId].value !== undefined
}

const imageProperties = computed(() => {
    let res: Array<PropertyRef> = []
    globalStore.propertyList.forEach((p: Property) => {
        let propRef: PropertyRef = {
            propertyId: p.id,
            type: p.type,
            value: hasProperty(p.id) ? image.value.properties[p.id].value : undefined,
            imageSHA1: image.value.sha1
        }
        res.push(propRef)
    });
    return res
})

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
</script>


<template>
    <div class="modal" tabindex="-1" role="dialog" ref="modalElem" aria-hidden="true">
        <div class="modal-dialog modal-xl" role="document">
            <div class="modal-content" v-if="isActive">
                <div class="modal-header">
                    <h5 class="modal-title">Image: {{ image.sha1 }}</h5>
                    <button type="button" class="btn close" @click="hide">
                        <span aria-hidden="true">&times;</span>
                    </button>
                </div>
                <div class="modal-body">
                    <div class="row">
                        <div class="col">
                            <div class="text-center">
                                <img :src="image.url" class="border" />
                            </div>
                        </div>
                        <div class="col">
                            <div class="mt-2">
                                <!-- <p class="m-0">Metadata</p>
                                            <div class="ms-2">
                                                <div>
                                                    <i class="bi bi-card-image"></i>
                                                    <span class="ms-2">{{ image.sha1 }}</span>
                                                </div>

                                                <div>
                                                    <i class="bi bi-aspect-ratio"></i>
                                                    <span class="ms-2">{{ image.width }} x {{ image.height }}</span>
                                                </div>

                                                <div>
                                                    <span class="bi bi-folder" v-for="path in image.paths">
                                                        <span class="ms-2">{{ path }}</span>
                                                    </span>

                                                </div>
                                            </div> -->
                                <!-- <p class="m-0">Properties</p> -->
                                <table class="table">
                                    <!-- <tbody> -->
                                        <tr v-for="property in imageProperties" class="">
                                            <td>{{ globalStore.properties[property.propertyId].name }}</td>
                                            <td class="w-100">
                                                <TagInput v-if="property.type == PropertyType.multi_tags"
                                                    :property="property" />
                                                <TagInput v-else-if="property.type == PropertyType.tag" :property="property"
                                                    :mono-tag="true" />
                                                <PropertyInput v-else :property="property" />
                                            </td>

                                        </tr>
                                    <!-- </tbody> -->
                                </table>
                            </div>
                        </div>
                    </div>




                </div>
                <div class="modal-footer">
                    <!-- <button type="button" class="btn btn-primary">Save changes</button> -->
                    <button type="button" class="btn btn-secondary" @click="hide">Close</button>
                </div>
            </div>
        </div>
    </div>
</template>