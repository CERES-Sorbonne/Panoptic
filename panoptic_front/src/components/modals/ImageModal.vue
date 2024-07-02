<script setup lang="ts">
import { Instance, ModalId, PropertyType } from '@/data/models';
import { Ref, computed, nextTick, provide, reactive, ref, shallowRef, watch } from 'vue';
import CenteredImage from '../images/CenteredImage.vue';
import ImagePropertyCol from './image/ImagePropertyCol.vue';
import { GroupManager, ImageIterator, SelectedImages } from '@/core/GroupManager';
import MiddleCol from './image/MiddleCol.vue';
import { usePanopticStore } from '@/data/panopticStore';
import { keyState } from '@/data/keyState';
import Modal2 from './Modal2.vue';
import { useDataStore } from '@/data/dataStore';

const panoptic = usePanopticStore()
const data = useDataStore()

const groupManager = new GroupManager()

const historyElem = ref(null)
const colElem = ref(null)
const colWidth = ref(0)
const colHeight = ref(0)
const viewMode = ref(0)
const visibleProperties = reactive({})
const navigationHistory: Ref<ImageIterator[]> = ref([])
const iterator: Ref<ImageIterator> = ref(null)
const preview = shallowRef<SelectedImages>({})

const active = computed(() => panoptic.openModalId == ModalId.IMAGE)
// const iterator = computed(() => panoptic.modalData as ImageIterator)
const image = computed(() => iterator.value?.image as Instance)

const modalData = computed(() => panoptic.modalData)
const showHistory = computed(() => navigationHistory.value.length > 0)

provide('nextImage', nextImage)
provide('prevImage', prevImage)
provide('showHistory', showHistory)

function onResize() {
    if (colElem.value) {
        colWidth.value = colElem.value.clientWidth
        colHeight.value = colElem.value.clientHeight
    }
}

function onHover() {
    preview.value = {}
    if(Object.keys(groupManager.selectedImages.value).length) {
        Object.keys(groupManager.selectedImages.value).forEach(i => preview.value[i] = true)
    } else {
        groupManager.result.root.images.forEach(i => preview.value[i.id] = true)
    }
}

function onHoverEnd() {
    preview.value = {}
}

function paint(propRef: { propertyId: number, instanceId: number }) {
    if (viewMode.value != 0) return
    const property = data.properties[propRef.propertyId]
    const value = data.instances[propRef.instanceId].properties[property.id]
    let images = groupManager.result.root.images
    if (Object.keys(groupManager.selectedImages.value).length) {
        images = Object.keys(groupManager.selectedImages.value).map(id => data.instances[id])
    }
    if (property.type == PropertyType.multi_tags) {
        data.setTagPropertyValue(property.id, images, value)
    } else {
        data.setPropertyValue(property.id, images, value)
    }
    visibleProperties[property.id] = true
}

function onShow() {
    navigationHistory.value = []
    // onModalDataChange()
}

function onHide() {
    iterator.value = undefined
    navigationHistory.value = []
    groupManager.clearSelection()
}

async function onModalDataChange(value: ImageIterator) {
    if (panoptic.openModalId != ModalId.IMAGE) return


    if (iterator.value) {
        navigationHistory.value.push(iterator.value)
        await nextTick()
        if (historyElem.value) {
            historyElem.value.scrollTop = historyElem.value.scrollHeight
        }

    }
    iterator.value = value
}

function nextImage() {
    const next = iterator.value.nextImages()
    if (next) {
        iterator.value = next
        clearNavigationHistory()
    }
}

function prevImage() {
    const prev = iterator.value.prevImages()
    if (prev) {
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
watch(() => keyState.left, (state) => {
    if (!active.value) return
    if (state && !showHistory.value) {
        prevImage()
    }
})
watch(() => keyState.right, (state) => {
    if (!active.value) return
    if (state && !showHistory.value) {
        nextImage()
    }
})
</script>

<template>
    <Modal2 :id="ModalId.IMAGE" @resize="onResize" @show="onShow" @hide="onHide">
        <template #title><b>ID: {{ image.id }}</b> | {{ image.width }} x {{ image.height }} | {{ image.name
            }}</template>
        <template #content="{ data }">
            <div class="h-100" v-if="image">
                <div class="d-flex h-100">
                    <ImagePropertyCol :image="iterator" :width="600" :image-height="500" :groupManager="groupManager"
                        :visible-properties="visibleProperties" @paint="paint"  @hover="onHover" @hoverEnd="onHoverEnd"/>
                    <div class="flex-grow-1 bg-white h-100 overflow-hidden" ref="colElem">
                        <MiddleCol :group-manager="groupManager" :height="colHeight" :width="colWidth" :image="image"
                            :mode="viewMode" :visible-properties="visibleProperties" @update:mode="e => viewMode = e"
                            :preview="preview"/>
                    </div>
                    <div class="history text-center" v-if="navigationHistory.length > 0" ref="historyElem">
                        <b>{{ $t('modals.image.history') }}</b>
                        <div v-for="it, index in navigationHistory" class="bordered">
                            <CenteredImage :image="it.image" :width="100" :height="100" @click="rollback(index)" />
                        </div>
                    </div>
                </div>
            </div>
        </template>
    </Modal2>
</template>

<style scoped>
.image-container {
    width: 400px;
    /* height: 400px; */
}

.history {
    background-color: var(--tab-grey);
    width: 130px;
    height: 100%;
    overflow: scroll;
    padding: 20px 12px;
}

.bordered {
    border: 1px solid var(--border-color);
    background-color: white;
    width: 102px;
    height: 102px;
    margin-bottom: 10px;
}
</style>