<script setup lang="ts">
import { Group, GroupData, Image, PropertyMode, PropertyRef, PropertyType, Sha1Pile } from '@/data/models';
import { globalStore } from '@/data/store';
import * as bootstrap from 'bootstrap';
import { ref, onMounted, watch, computed } from 'vue';
import PropertyInput from '../inputs/PropertyInput.vue';
import TagInput from '../inputs/TagInput.vue';
import GridScroller from '../scrollers/grid/GridScroller.vue';

const modalElem = ref(null)
let modal: bootstrap.Modal = null

const props = defineProps({
    id: { type: String, required: true }
})

const pile = computed(() => globalStore.openModal.data as Sha1Pile)
const isActive = computed(() => globalStore.openModal.id == props.id)
const similarImages = ref([])
const nbSimilarImages = ref(10)
const availableHeight = ref(100)

const image = computed(() => pile.value.images[0])

function hasProperty(image: Image, propertyId: number) {
    return image.properties[propertyId] && image.properties[propertyId].value !== undefined
}

function getImageProperties(id: number) {
    const img = globalStore.images[id]
    let res = globalStore.propertyList.filter(p => p.mode == PropertyMode.id).map(p => {
        let propRef: PropertyRef = {
            propertyId: p.id,
            type: p.type,
            value: hasProperty(img, p.id) ? img.properties[p.id].value : undefined,
            imageId: img.id,
            mode: p.mode
        }
        return propRef
    })
    return res
}

function getSha1Properties(sha1: string) {
    const img = globalStore.sha1Index[sha1][0]
    let res = globalStore.propertyList.filter(p => p.mode == PropertyMode.sha1).map(p => {
        let propRef: PropertyRef = {
            propertyId: p.id,
            type: p.type,
            value: hasProperty(img, p.id) ? img.properties[p.id].value : undefined,
            imageId: img.id,
            mode: p.mode
        }
        return propRef
    })
    return res
}

const properties = computed(() => getSha1Properties(pile.value.sha1))

const sha1Properties = computed(() => properties.value.filter(p => p.mode == 'sha1'))
const imgProperties = computed(() => {
    let res: { [key: number]: PropertyRef[] } = {}
    pile.value.images.forEach(img => res[img.id] = getImageProperties(img.id))
    return res
})
const groupData = computed(() => {
    let group: Group = {
        id: '0',
        name: '__all__',
        images: pile.value.images,
        groups: undefined,
        depth: 0,
        propertyValues: [],
        parentId: undefined,
        count: pile.value.images.length
    }
    let index = {}
    index[group.id] = group
    return {
        root: group,
        index,
        order: [group.id]
    } as GroupData
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
    availableHeight.value = modalElem.value.clientHeight
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

</script>


<template>
    <div class="modal" tabindex="-1" role="dialog" ref="modalElem" aria-hidden="true">
        <div class="modal-dialog modal-xl" role="document">
            <div class="modal-content" v-if="isActive">
                <div class="modal-header" style="height: 40px;">
                    <h5 class="modal-title">Sha1: {{ image.sha1 }}</h5>
                    <button type="button" class="btn close" @click="hide">
                        <span aria-hidden="true">&times;</span>
                    </button>
                </div>
                <div class="modal-body" style="max-height: calc(100vh - 100px); overflow-x: hidden; overflow-y: scroll;">
                    <div class="row">
                        <div class="col">
                            <div class="text-center mb-2">
                                <img :src="image.fullUrl" class="border image-size" />
                            </div>
                        </div>
                        <div class="col" style="height: 400px; overflow: scroll;">
                            <div class="mt-2">
                                <table class="table">
                                    <b>Proprietés</b>
                                    <tr v-for="property, index in sha1Properties" class="">
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
                                    <tr v-for="property, index in sha1Properties" class="">
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
                            </div>
                        </div>
                    </div>
                    <div class="m-0 p-0" style="width: 1100px; overflow-x: overlay; overflow-y: hidden;">
                        <GridScroller :show-images="false" :data="groupData" :height="availableHeight - 550" :selected-properties="globalStore.propertyList.filter(p => p.mode == PropertyMode.id)"/>
                    </div>

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