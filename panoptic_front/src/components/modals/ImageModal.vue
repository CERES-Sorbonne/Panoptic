<script setup lang="ts">
import { GroupData, Image, Modals, Property, PropertyRef, PropertyType } from '@/data/models';
import { globalStore } from '@/data/store';
import * as bootstrap from 'bootstrap';
import { ref, onMounted, watch, computed, reactive } from 'vue';
import PropertyInput from '../inputs/PropertyInput.vue';
import TagInput from '../inputs/TagInput.vue';
import StampDropdown from '../inputs/StampDropdown.vue';
import ImageSimi from '../images/ImageSimi.vue'
import RangeInput from '../inputs/RangeInput.vue';
import GridScroller from '../scrollers/grid/GridScroller.vue';
import { generateGroups } from '@/utils/groups';
import TreeScroller from '../scrollers/tree/TreeScroller.vue';

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

const groupData = reactive({
    root: undefined,
    index: {},
    order: []
}) as GroupData

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
}

function show() {
    modal.show()
    availableHeight.value = modalElem.value.clientHeight
    availableWidth.value = modalElem.value.clientWidth
    console.log(availableWidth.value)
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
    // console.log(res)
    // console.log(globalStore.sha1Index)
    similarImages.value = res.map((i:any) => ({ url: globalStore.sha1Index[i.sha1][0].url, dist: i.dist, sha1: i.sha1, id:globalStore.sha1Index[i.sha1][0].id }))
    
    // for(let img of res) {
    //     console.log(img.sha1, globalStore.sha1Index[img.sha1])
    // }
    var imgs = res.map(r => globalStore.sha1Index[r.sha1][0])
    var index = generateGroups(imgs, [])
    groupData.index = index
    groupData.root = index[0]
    groupData.order = ['0']
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
                <div class="modal-body overflow-scroll" style="max-height: calc(100vh - 100px);">
                    <div class="row">
                        <div class="col">
                            <div class="text-center mb-2">
                                <img :src="image.fullUrl" class="border image-size" />
                            </div>

                            <div class="mt-2" :style="{height: (availableHeight - 550)+'px', overflow: 'scroll'}">
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
                            <button class="me-2" @click="setSimilar()">Find Similar</button>
                            <TreeScroller :image-size="80" :height="availableHeight - 170" :width="availableWidth - 1000" :data="groupData" :properties="[globalStore.propertyList[1]]" ref="scroller" :hideRoot="true"/>
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
</style>