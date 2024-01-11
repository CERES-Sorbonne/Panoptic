<script setup lang="ts">
import { Image, ModalId } from '@/data/models';
import Modal from './Modal.vue';
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue';
import { useProjectStore } from '@/data/projectStore';
import CenteredImage from '../images/CenteredImage.vue';
import ImagePropertyCol from './image/ImagePropertyCol.vue';
import { GroupManager } from '@/core/GroupManager';
import TreeScroller from '../scrollers/tree/TreeScroller.vue';
import { getSimilarImages } from '@/utils/utils';
import SelectionStamp from '../selection/SelectionStamp.vue';
import RangeInput from '../inputs/RangeInput.vue';
import SelectCircle from '../inputs/SelectCircle.vue';
import Similarity from './image/Similarity.vue';
import MiddleCol from './image/MiddleCol.vue';

const project = useProjectStore()

const similarGroup = new GroupManager()


const colElem = ref(null)
const colWidth = ref(0)
const colHeight = ref(0)
const viewMode = ref(0)
const image = computed(() => project.imageList[1])



function onResize() {
    if (colElem.value) {
        colWidth.value = colElem.value.clientWidth
        colHeight.value = colElem.value.clientHeight
    }
}

watch(colElem, onResize)
</script>

<template>
    <Modal :id="ModalId.TEST" @resize="onResize">
        <template #content>
            <div class="h-100" v-if="image">
                <div class="d-flex h-100">
                    <ImagePropertyCol :image="image" :width="500" :image-height="400" />
                    <div class="flex-grow-1 bg-white h-100 overflow-hidden" ref="colElem">
                        <MiddleCol :group-manager="similarGroup" :height="colHeight" :width="colWidth" :image="image" :mode="viewMode" @update:mode="e => viewMode = e"/>
                        
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