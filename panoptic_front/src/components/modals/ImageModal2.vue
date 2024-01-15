<script setup lang="ts">
import { Image, ModalId, Property, PropertyRef } from '@/data/models';
import Modal from './Modal.vue';
import { Ref, computed, nextTick, onMounted, provide, reactive, ref, vModelDynamic, watch } from 'vue';
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
import { props } from '../Scroller/src/components/common';

const panoptic = usePanopticStore()
const project = useProjectStore()

const groupManager = new GroupManager()

const historyElem = ref(null)
const colElem = ref(null)
const colWidth = ref(0)
const colHeight = ref(0)
const viewMode = ref(0)
const visibleProperties = reactive({})
const navigationHistory: Ref<ImageIterator[]> = ref([])
const iterator: Ref<ImageIterator> = ref(null)

// const iterator = computed(() => panoptic.modalData as ImageIterator)
const image = computed(() => iterator.value?.image as Image)

const modalData = computed(() => panoptic.modalData)
const showHistory = computed(() => navigationHistory.value.length > 0)

provide('nextImage', nextImage)
provide('prevImage', prevImage)
provide('showHistory', showHistory)

function onResize() {
    console.log('showHistory', showHistory.value)
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
    navigationHistory.value = []
    // onModalDataChange()
}

function onHide() {
    navigationHistory.value = []
}

async function onModalDataChange(value: ImageIterator) {
    if(panoptic.openModalId != ModalId.TEST) return

    
    if(iterator.value) {
        navigationHistory.value.push(iterator.value)
        await nextTick()
        if(historyElem.value) {
            historyElem.value.scrollTop = historyElem.value.scrollHeight
        }
        
    }
    iterator.value = value
}

function nextImage() {
    const next = iterator.value.nextImages()
    if(next) {
        iterator.value = next
        clearNavigationHistory()
    }
}

function prevImage() {
    const prev = iterator.value.prevImages()
    if(prev) {
        iterator.value = prev
        clearNavigationHistory()
    }
}

function clearNavigationHistory() {
    navigationHistory.value = []
}

function rollback(index) {
    iterator.value = navigationHistory.value[index]
    navigationHistory.value.splice(index)
}

watch(showHistory, () => nextTick(onResize))
watch(colElem, onResize)
watch(modalData, onModalDataChange)
</script>

<template>
    <Modal :id="ModalId.TEST" @resize="onResize" @show="onShow" @hide="onHide">
        <template #content="{ data }">
            <div class="h-100" v-if="image">
                <div class="d-flex h-100">
                    <ImagePropertyCol :image="iterator" :width="500" :image-height="400"
                        :visible-properties="visibleProperties" @paint="paint"/>
                    <div class="flex-grow-1 bg-white h-100 overflow-hidden" ref="colElem">
                        <MiddleCol :group-manager="groupManager" :height="colHeight" :width="colWidth" :image="image"
                            :mode="viewMode" :visible-properties="visibleProperties" @update:mode="e => viewMode = e" />
                    </div>
                    <div class="history" v-if="navigationHistory.length > 0" ref="historyElem">
                        <div v-for="it, index in navigationHistory" class="bordered">
                            <CenteredImage :image="it.image" :width="100" :height="100" @click="rollback(index)"/>
                        </div>
                    </div>
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

.history {
    background-color: var(--tab-grey);
    width: 140px;
    height: 100%;
    overflow: scroll;
    padding: 20px 20px;
}

.bordered {
    border: 1px solid var(--border-color);
    background-color: white;
    width: 102px;
    height: 102px;
    margin-bottom: 10px;
}
</style>