<script setup lang="ts">
import { Image, Property, PropertyMode, PropertyRef, Sha1Scores } from '@/data/models';
import * as bootstrap from 'bootstrap';
import { ref, onMounted, watch, computed, reactive } from 'vue';
import PropertyInput from '../inputs/PropertyInput.vue';
import RangeInput from '../inputs/RangeInput.vue';
import GridScroller from '../scrollers/grid/GridScroller.vue';
import TreeScroller from '../scrollers/tree/TreeScroller.vue';
import PropInput from '../inputs/PropInput.vue';
import PropertyIcon from '../properties/PropertyIcon.vue';
import SelectionStamp from '../selection/SelectionStamp.vue';
import wTT from '../tooltips/withToolTip.vue'
import SelectCircle from '../inputs/SelectCircle.vue';
import { GroupManager } from '@/core/GroupManager';
import { SortManager } from '@/core/SortManager';
import { CollectionManager } from '@/core/CollectionManager';
import { useStore } from '@/data/store';
import { getSimilarImages } from '@/utils/utils';

const store = useStore()

const modalElem = ref(null)
let modal: bootstrap.Modal = null

const props = defineProps({
    id: { type: String, required: true }
})

const state = reactive({
    sha1Scores: {} as Sha1Scores
})

const similarGroup = new GroupManager()
similarGroup.setSha1Mode(true)

const image = computed(() => store.openModal.data as Image)
const isActive = computed(() => store.openModal.id == props.id)
const similarImages = ref([])
const availableHeight = ref(100)
const availableWidth = ref(100)
const scroller = ref(null)
const minSimilarityDist = ref(80)
const similarityLoaded = computed(() => similarGroup.hasResult() != undefined)

const similarityVisibleProps = reactive({})
const similarityVisiblePropsList = computed(() => Object.keys(similarityVisibleProps).map(Number).map(pId => store.data.properties[pId]))

const selectedImages = reactive({})

function hasSha1Property(image: Image, propertyId: number) {
    return image.properties[propertyId] && image.properties[propertyId].value !== undefined
}

function getSha1Properties(sha1: string) {
    const img = store.data.sha1Index[sha1][0]
    let res = store.propertyList.filter(p => p.mode == PropertyMode.sha1).map(p => {
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

const sha1Images = computed(() => store.data.sha1Index[image.value.sha1])
const properties = computed(() => getSha1Properties(image.value.sha1))
const sha1Properties = computed(() => properties.value.filter(p => p.mode == 'sha1'))
const selectedImageIds = computed(() => Object.keys(similarGroup.selectedImages).map(Number))
const hasSelectedImages = computed(() => Object.keys(similarGroup.selectedImages).length > 0)

enum ImageModalMode {
    Similarity = 'similarity',
    Unique = 'unique'
}

const modalMode = ref(ImageModalMode.Similarity)

const identiqueImages = new CollectionManager()

const containerStyle = ref("")

function hasProperty(propertyId: number) {
    return image.value.properties[propertyId] && image.value.properties[propertyId].value !== undefined
}

const imageProperties = computed(() => {
    let res: Array<PropertyRef> = []
    store.propertyList.forEach((p: Property) => {
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

const hasUniqueProperties = computed(() => store.propertyList.some(p => p.mode == PropertyMode.id))

function onHide() {
    if (store.openModal.id == props.id) {
        store.hideModal()
    }
}

function hide() {
    // if (groupData.root) selector.clear()
    modal.hide()

    similarGroup.clear()
    similarImages.value = []
}

function show() {
    modal.show()
    availableHeight.value = modalElem.value.clientHeight
    availableWidth.value = modalElem.value.clientWidth
    
    identiqueImages.update(sha1Images.value)
    if (similarGroup.hasResult()) {
        similarGroup.clear()
    }
    setSimilar()
}

function toggleProperty(propId: Number) {
    if (similarityVisibleProps[String(propId)]) {
        delete similarityVisibleProps[String(propId)]
    }
    else {
        similarityVisibleProps[String(propId)] = true
    }
}

watch(() => store.openModal.id, (id) => {
    console.log('change')
    if (id == props.id) {
        show()
    }
    else {
        hide()
    }
})

watch(image, () => {
    if (store.openModal.id == props.id) {
        show()
    }
})

watch(modalMode, () => {
    if (modalMode.value == ImageModalMode.Similarity && similarImages.value.length == 0) {
        setSimilar()
    }
})

onMounted(() => {
    modal = bootstrap.Modal.getOrCreateInstance(modalElem.value)
    modalElem.value.addEventListener('hide.bs.modal', onHide)
})

async function setSimilar() {
    if (modalMode.value != ImageModalMode.Similarity) return

    const res = await getSimilarImages(image.value.sha1)
    similarImages.value = res
    updateSimilarGroup()
}

function updateSimilarGroup() {
    var filteredSha1s = similarImages.value.filter(i => i.dist >= (minSimilarityDist.value / 100.0))

    const images: Image[] = []
    state.sha1Scores = {}
    filteredSha1s.forEach(r => images.push(...store.data.sha1Index[r.sha1]))
    filteredSha1s.forEach(r => state.sha1Scores[r.sha1] = r.dist)

    const sorter = new SortManager()
    const res = sorter.sort(images)
    similarGroup.group(res.images, res.order)

    if (scroller.value) {
        scroller.value.computeLines()
        scroller.value.scrollTo('0')
    }

}

function paintSelection(property: PropertyRef) {
    let images = similarGroup.result.root.images
    if (Object.keys(similarGroup.selectedImages).length) {
        images = Object.keys(similarGroup.selectedImages).map(id => store.data.images[id])
    }
    store.setPropertyValue(property.propertyId, images, property.value)
}

watch(minSimilarityDist, updateSimilarGroup)

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
                <div class="modal-body pt-1 pb-1" style="max-height: calc(100vh - 100px);">
                    <div class="d-flex justify-content-center mb-1">
                        <div class="d-flex border rounded overflow-hidden">
                            <wTT message="modals.image.similar_images_tooltip">
                                <div class="ps-2 pe-2 btn-icon"
                                    :class="(modalMode == ImageModalMode.Similarity ? 'selected' : '')"
                                    @click="modalMode = ImageModalMode.Similarity">{{ $t('modals.image.similar_images') }}
                                </div>
                            </wTT>
                            <div class="border-start" v-if="hasUniqueProperties"></div>
                            <wTT message="modals.image.unique_properties_tooltip" v-if="hasUniqueProperties">
                                <div class="ps-2 pe-2 btn-icon"
                                    :class="(modalMode == ImageModalMode.Unique ? 'selected' : '')"
                                    @click="modalMode = ImageModalMode.Unique">
                                    {{ $t('modals.image.unique_properties') }}</div>
                            </wTT>
                        </div>

                    </div>
                    <div class="row" v-if="modalMode == ImageModalMode.Similarity">
                        <div class="col overflow-hidden" :style="'width: 600px;' + containerStyle">
                            <div class="mb-2 image-container">
                                <img :src="image.fullUrl" class=""
                                    @mouseover="containerStyle = 'overflow: visible !important;'"
                                    @mouseleave="containerStyle = ''" />
                            </div>

                            <div class="mt-2"
                                :style="{ height: (availableHeight - 560) + 'px', overflow: 'scroll', width: '550px' }">
                                <!-- <p class="m-0">Properties</p> -->
                                <table class="table table-bordered table-sm" style="width: 500px;">

                                    <b>Proprietés</b>
                                    <tbody>
                                        <tr v-for="property, index in sha1Properties" class="">
                                            <template v-if="property.propertyId >= 0">
                                                <td class="text-nowrap">
                                                    <PropertyIcon :type="property.type" /> {{
                                                        store.data.properties[property.propertyId].name }}
                                                </td>
                                                <td class="ps-1" style="width: 100%;">
                                                    <PropInput :property="store.data.properties[property.propertyId]"
                                                        :image="image" :width="-1" :min-height="20" />
                                                </td>

                                                <td class="text-center btn-icon" style="width: 20px;"
                                                    @click="toggleProperty(property.propertyId)">
                                                    <wTT message="modals.image.toggle_property_tooltip">
                                                        <i class="bi bi-eye"
                                                            :class="(similarityVisibleProps[property.propertyId] ? 'text-primary' : '')" />
                                                    </wTT>
                                                </td>


                                                <td class="text-center btn-icon"
                                                    style="padding: 4px 2px 0px 5px; width: 20px;"
                                                    @click="paintSelection(property)">
                                                    <wTT message="modals.image.fill_property_tooltip">
                                                        <i class="bi bi-paint-bucket"></i>
                                                    </wTT>
                                                </td>
                                            </template>
                                        </tr>
                                    </tbody>
                                </table>

                                <table class="table">
                                    <b>Computed</b>
                                    <tr v-for="property, index in imageProperties" class="">
                                        <template v-if="property.propertyId < 0">
                                            <td>{{ store.data.properties[property.propertyId].name }}</td>
                                            <td class="w-100">
                                                <PropertyInput :property="property" :input-id="[100, index]" />
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
                        <div class="col" v-if="similarityLoaded">
                            <!-- <button class="me-2" @click="setSimilar()">Find Similar</button> -->
                            <div class="d-flex mb-1">
                                <SelectCircle v-if="similarGroup.hasResult()"
                                    :model-value="similarGroup.result.root.view.selected"
                                    @update:model-value="v => similarGroup.toggleAll()" />
                                <div style="margin-left: 6px;" class="me-3">Images Similaires</div>
                                <wTT message="modals.image.similarity_filter_tooltip">
                                    <RangeInput class="me-2" :min="0" :max="100" v-model="minSimilarityDist"
                                        @update:model-value="similarGroup.clearSelection()" />
                                </wTT>
                                <div>min: {{ minSimilarityDist }}%</div>
                                <div v-if="similarGroup.hasResult()" class="ms-2 text-secondary">({{
                                    similarGroup.result.root.children.length }} images)</div>
                            </div>

                            <div class="selection-stamp" v-if="hasSelectedImages">
                                <SelectionStamp :selected-images-ids="selectedImageIds"
                                    @remove:selected="similarGroup.clearSelection()" />
                            </div>
                            <TreeScroller :image-size="70" :height="availableHeight - 180" :width="510"
                                :group-manager="similarGroup" :properties="similarityVisiblePropsList"
                                :sha1-scores="state.sha1Scores" :hide-options="true" :hide-group="true" ref="scroller" />
                        </div>
                    </div>

                    <div class="row" v-else>
                        <div class="col">
                            <div class="text-center mb-2 image-container">
                                <img :src="image.fullUrl" />
                            </div>
                        </div>
                        <div class="col" style="height: 400px; overflow: scroll;">
                            <div class="mt-2">
                                <table class="table table-bordered table-sm">

                                    <b>Proprietés</b>
                                    <tbody>
                                        <tr v-for="property, index in sha1Properties" class="">
                                            <template v-if="property.propertyId >= 0">
                                                <td class="text-nowrap">
                                                    <PropertyIcon :type="property.type" /> {{
                                                        store.data.properties[property.propertyId].name }}
                                                </td>
                                                <td>
                                                    <PropInput :property="store.data.properties[property.propertyId]"
                                                        :image="image" :width="400" :min-height="20" />
                                                </td>
                                            </template>
                                        </tr>
                                    </tbody>
                                </table>

                                <table class="table">
                                    <b>Computed</b>
                                    <tr v-for="property, index in imageProperties" class="">
                                        <template v-if="property.propertyId < 0">
                                            <td>{{ store.data.properties[property.propertyId].name }}</td>
                                            <td class="w-100">
                                                <PropertyInput :property="property" :input-id="[100, index]" />
                                            </td>
                                        </template>

                                    </tr>
                                </table>
                            </div>
                        </div>
                        <div class="m-0 p-0" style="width: 1140px; overflow-x: scroll; overflow-y: hidden;">
                            <GridScroller :show-images="true" :manager="identiqueImages.groupManager" :height="availableHeight - 570"
                                :selected-properties="store.propertyList.filter(p => p.mode == PropertyMode.id)" />
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
/* .image-size {
    max-width: 500px;
    max-height: 400px;
} */

.selection-stamp {
    position: absolute;
    top: 8px;
    right: 50px;
}

.image-container {
    width: 540px;
    height: 400px;
    position: relative;
    margin: auto;
    padding: auto;
    border: 1px solid var(--border-color);
}

img {
    max-height: 100%;
    max-width: 100%;
    /* width: auto;
    height: auto; */
    position: absolute;
    top: 0;
    bottom: 0;
    left: 0;
    right: 0;
    margin: auto;
    transition: 0.1s;
}

img:hover {
    -ms-transform: scale(3);
    /* IE 9 */
    -webkit-transform: scale(3);
    /* Safari 3-8 */
    transform: scale(2);
    z-index: 999;
    margin-top: 6em;
    box-shadow: 0px 0px 50px 100px rgba(115, 115, 115, 0.53);
    -webkit-box-shadow: 0px 0px 50px 36px rgba(115, 115, 115, 0.53);
}

.selected {
    background-color: var(--light-grey);
}
</style>