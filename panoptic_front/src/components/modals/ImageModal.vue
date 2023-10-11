<script setup lang="ts">
import { GroupData, Image, Modals, Property, PropertyMode, PropertyRef, PropertyType } from '@/data/models';
import { globalStore } from '@/data/store';
import * as bootstrap from 'bootstrap';
import { ref, onMounted, watch, computed, reactive } from 'vue';
import PropertyInput from '../inputs/PropertyInput.vue';
import TagInput from '../inputs/TagInput.vue';
import StampDropdown from '../inputs/StampDropdown.vue';
import ImageSimi from '../images/ImageSimi.vue'
import RangeInput from '../inputs/RangeInput.vue';
import GridScroller from '../scrollers/grid/GridScroller.vue';
import { generateGroups, imagesToSha1Piles } from '@/utils/groups';
import TreeScroller from '../scrollers/tree/TreeScroller.vue';
import { Group } from '@/data/models';

const modalElem = ref(null)
let modal: bootstrap.Modal = null

const props = defineProps({
    id: { type: String, required: true }
})

const image = computed(() => globalStore.openModal.data as Image)
const isActive = computed(() => globalStore.openModal.id == props.id)
const similarImages = ref([])
const nbSimilarImages = ref(10)
const availableHeight = ref(100)
const availableWidth = ref(100)
const scroller = ref(null)

function hasSha1Property(image: Image, propertyId: number) {
    return image.properties[propertyId] && image.properties[propertyId].value !== undefined
}

function getSha1Properties(sha1: string) {
    const img = globalStore.sha1Index[sha1][0]
    let res = globalStore.propertyList.filter(p => p.mode == PropertyMode.sha1).map(p => {
        let propRef: PropertyRef = {
            propertyId: p.id,
            type: p.type,
            value: hasSha1Property(img, p.id) ? img.properties[p.id].value : undefined,
            imageId: img.id,
            mode: p.mode
        }
        return propRef
    })
    return res
}

const pile = computed(() => ({ sha1: image.value.sha1, images: globalStore.sha1Index[image.value.sha1] }))
const properties = computed(() => getSha1Properties(pile.value.sha1))
const sha1Properties = computed(() => properties.value.filter(p => p.mode == 'sha1'))

enum ImageModalMode {
    Similarity = 'similarity',
    Unique = 'unique'
}

const modalMode = ref(ImageModalMode.Similarity)

const groupData = reactive({
    root: undefined,
    index: {},
    order: []
}) as GroupData

const gridData = computed(() => {
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
            imageId: image.value.id,
            mode: p.mode
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
    groupData.root = undefined
    groupData.index = {}
    groupData.order = []
}

function show() {
    modal.show()
    availableHeight.value = modalElem.value.clientHeight
    availableWidth.value = modalElem.value.clientWidth
    setSimilar()
}

watch(() => globalStore.openModal.id, (id) => {
    console.log('change')
    if (id == props.id) {
        show()
    }
    else {
        hide()
        similarImages.value = []
    }
})

watch(image, () => { 
    if (globalStore.openModal.id == props.id) {
        show()
    }
})

onMounted(() => {
    modal = bootstrap.Modal.getOrCreateInstance(modalElem.value)
    modalElem.value.addEventListener('hide.bs.modal', onHide)
})

const setSimilar = async () => {
    const res = await globalStore.getSimilarImages(image.value.sha1)
    var imgs = res.map(r => globalStore.sha1Index[r.sha1][0])
    var index = generateGroups(imgs, [])
    groupData.index = index
    groupData.root = index[0]
    groupData.root.name = 'Similar Images'
    groupData.order = ['0']

    groupData.root.imagePiles = []
    res.forEach(r => groupData.root.imagePiles.push({ sha1: r.sha1, images: globalStore.sha1Index[r.sha1], similarity: r.dist }))

    scroller.value.computeLines()
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
                <div class="modal-body overflow-scroll pt-1 pb-1" style="max-height: calc(100vh - 100px);">
                    <div class="d-flex justify-content-center mb-1">
                        <div class="d-flex border rounded overflow-hidden">
                            <div class="ps-2 pe-2 btn-icon"
                                :class="(modalMode == ImageModalMode.Similarity ? 'selected' : '')"
                                @click="modalMode = ImageModalMode.Similarity">Images Similaires</div>
                            <div class="border-start"></div>
                            <div class="ps-2 pe-2 btn-icon" :class="(modalMode == ImageModalMode.Unique ? 'selected' : '')"
                                @click="modalMode = ImageModalMode.Unique">
                                Proprietées uniques</div>
                        </div>

                    </div>
                    <div class="row" v-if="modalMode == ImageModalMode.Similarity">
                        <div class="col overflow-hidden" style="width: 600px;">
                            <div class="text-center mb-2">
                                <img :src="image.fullUrl" class="border image-size" />
                            </div>

                            <div class="mt-2" :style="{ height: (availableHeight - 540) + 'px', overflow: 'scroll' }">
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
                            </div>
                            <!-- <div id="similarImages" v-if="similarImages.length > 0">
                                <RangeInput :min="0" :max="50" v-model="nbSimilarImages"/>
                                <StampDropdown
                                    :images="[image, ...similarImages.slice(0, nbSimilarImages).map(i => globalStore.images[i.id])]" />
                                <div class="m-2">
                                    <div class="d-flex flex-wrap">
                                        <ImageSimi :image="Object.assign(img, globalStore.images[img.id])" :size="100" v-for="img in similarImages.slice(0, nbSimilarImages)" />
                                    </div>

                                </div>
                            </div> -->
                        </div>
                        <div class="col">
                            <!-- <button class="me-2" @click="setSimilar()">Find Similar</button> -->
                            <TreeScroller :image-size="70" :height="availableHeight - 150" :width="availableWidth - 930"
                                :data="groupData" :properties="[globalStore.propertyList[1]]" ref="scroller"
                                :hide-options="true" />
                        </div>
                    </div>

                    <div class="row" v-else>
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
                        <div class="m-0 p-0" style="width: 1100px; overflow-x: overlay; overflow-y: hidden;">
                            <GridScroller :show-images="false" :data="gridData" :height="availableHeight - 550"
                                :selected-properties="globalStore.propertyList.filter(p => p.mode == PropertyMode.id)" />
                        </div>
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

.selected {
    background-color: var(--light-grey);
}
</style>