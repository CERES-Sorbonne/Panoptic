<script setup lang="ts">
import { Image, Modals, Property, PropertyRef, PropertyType } from '@/data/models';
import { globalStore } from '@/data/store';
import * as bootstrap from 'bootstrap';
import { ref, onMounted, watch, computed } from 'vue';
import PropertyInput from '../inputs/PropertyInput.vue';
import TagInput from '../inputs/TagInput.vue';
import StampDropdown from '../inputs/StampDropdown.vue';
import PaginatedImages from '../images/PaginatedImages.vue';
import ImageSimi from '../images/ImageSimi.vue'
import RangeInput from '../inputs/RangeInput.vue';

const modalElem = ref(null)
let modal: bootstrap.Modal = null

const props = defineProps({
    id: { type: String, required: true }
})

const image = computed(() => globalStore.openModal.data as Image)
const isActive = computed(() => globalStore.openModal.id == props.id)
const similarImages = ref([])
const nbSimilarImages = ref(10)

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
            imageId: image.value.id
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
        similarImages.value = []
    }
})

onMounted(() => {
    modal = bootstrap.Modal.getOrCreateInstance(modalElem.value)
    modalElem.value.addEventListener('hide.bs.modal', onHide)
})

const setSimilar = async () => {
    const res = await globalStore.getSimilarImages(image.value.sha1)
    similarImages.value = res.map((i:any) => ({ url: globalStore.sha1Index[i.sha1][0].url, dist: i.dist, sha1: i.sha1, id:globalStore.sha1Index[i.sha1][0].id }))
}
</script>


<template>
    <div class="modal" tabindex="-1" role="dialog" ref="modalElem" aria-hidden="true">
        <div class="modal-dialog modal-xl" role="document">
            <div class="modal-content" v-if="isActive">
                <div class="modal-header" style="height: 40px;">
                    <h5 class="modal-title">Image: {{ image.name }}</h5>
                    <button type="button" class="btn close" @click="hide">
                        <span aria-hidden="true">&times;</span>
                    </button>
                </div>
                <div class="modal-body">
                    <div class="row">
                        <div class="col">
                            <div class="text-center mb-2">
                                <img :src="image.fullUrl" class="border image-size" />
                            </div>
                            <div id="similarImages" v-if="similarImages.length > 0">
                                <RangeInput :min="0" :max="50" v-model="nbSimilarImages"/>
                                <StampDropdown
                                    :images="similarImages.slice(1, nbSimilarImages).map(i => globalStore.images[i.id])" />
                                <div class="m-2">
                                    <div class="d-flex flex-wrap">
                                        <ImageSimi :image="Object.assign(img, globalStore.images[img.id])" :size="100" v-for="img in similarImages.slice(0, nbSimilarImages)" />
                                    </div>

                                </div>
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
                                    <b>Proprietés</b>
                                    <tr v-for="property, index in imageProperties" class="">
                                        <template v-if="property.propertyId >= 0">
                                            <td>{{ globalStore.properties[property.propertyId].name }}</td>
                                            <td class="w-100">
                                                <TagInput v-if="property.type == PropertyType.multi_tags"
                                                    :property="property" :input-id="[100, index]" />
                                                <TagInput v-else-if="property.type == PropertyType.tag" :property="property"
                                                    :mono-tag="true" :input-id="[100, index]" />
                                                <PropertyInput v-else :property="property" :input-id="[100, index]" />
                                            </td>
                                        </template>

                                    </tr>
                                </table>

                                <table class="table">
                                    <b>Computed</b>
                                    <tr v-for="property, index in imageProperties" class="">
                                        <template v-if="property.propertyId < 0">
                                            <td>{{ globalStore.properties[property.propertyId].name }}</td>
                                            <td class="w-100">
                                                <TagInput v-if="property.type == PropertyType.multi_tags"
                                                    :property="property" :input-id="[100, index]" />
                                                <TagInput v-else-if="property.type == PropertyType.tag" :property="property"
                                                    :mono-tag="true" :input-id="[100, index]" />
                                                <PropertyInput v-else :property="property" :input-id="[100, index]" />
                                            </td>
                                        </template>

                                    </tr>
                                </table>
                                <button class="me-2" @click="setSimilar()">Find Similar</button>
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

<style scoped>
.image-size {
    max-width: 600px;
    max-height: 400px;
}
</style>