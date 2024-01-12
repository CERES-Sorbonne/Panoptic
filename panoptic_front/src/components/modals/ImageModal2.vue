<script setup lang="ts">
import { Image, ModalId, Property, PropertyRef } from '@/data/models';
import Modal from './Modal.vue';
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue';
import { useProjectStore } from '@/data/projectStore';
import CenteredImage from '../images/CenteredImage.vue';
import ImagePropertyCol from './image/ImagePropertyCol.vue';
import { GroupManager, ImageIterator } from '@/core/GroupManager';
import TreeScroller from '../scrollers/tree/TreeScroller.vue';
import { getSimilarImages } from '@/utils/utils';
import SelectionStamp from '../selection/SelectionStamp.vue';
import RangeInput from '../inputs/RangeInput.vue';
import SelectCircle from '../inputs/SelectCircle.vue';
import Similarity from './image/Similarity.vue';
import MiddleCol from './image/MiddleCol.vue';
import { usePanopticStore } from '@/data/panopticStore';

const panoptic = usePanopticStore()
const project = useProjectStore()

const groupManager = new GroupManager()


const colElem = ref(null)
const colWidth = ref(0)
const colHeight = ref(0)
const viewMode = ref(0)
const visibleProperties = reactive({})

const iterator = computed(() => panoptic.modalData)
const image = computed(() => iterator.value?.image)
// const iterator = ref(null as ImageIterator)

function onResize() {
    if (colElem.value) {
        colWidth.value = colElem.value.clientWidth
        colHeight.value = colElem.value.clientHeight
    }
}

function paint(property: PropertyRef) {
    if(viewMode.value != 0) return

    let images = groupManager.result.root.images
    if (Object.keys(groupManager.selectedImages).length) {
        images = Object.keys(groupManager.selectedImages).map(id => project.data.images[id])
    }
    project.setPropertyValue(property.propertyId, images, property.value)
    visibleProperties[property.propertyId] = true
}

function onShow() {
}

watch(colElem, onResize)
</script>

<template>
    <Modal :id="ModalId.TEST" @resize="onResize" @show="onShow">
        <template #content="{ data }">
            <div class="h-100" v-if="image">
                <div class="d-flex h-100">
                    <ImagePropertyCol :image="image" :width="500" :image-height="400"
                        :visible-properties="visibleProperties" @paint="paint"/>
                    <div class="flex-grow-1 bg-white h-100 overflow-hidden" ref="colElem">
                        <MiddleCol :group-manager="groupManager" :height="colHeight" :width="colWidth" :image="image"
                            :mode="viewMode" :visible-properties="visibleProperties" @update:mode="e => viewMode = e" />

                    </div>
                    <div class="bg-info h-100 p-5">History</div>
                </div>
            </div>
        </template>
    </Modal>
</template>

<style scoped>
.image-container {
    width: 400px;
    /* height: 400px; */
}
</style>