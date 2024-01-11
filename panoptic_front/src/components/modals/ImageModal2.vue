<script setup lang="ts">
import { ModalId } from '@/data/models';
import Modal from './Modal.vue';
import { computed } from 'vue';
import { useProjectStore } from '@/data/projectStore';
import CenteredImage from '../images/CenteredImage.vue';
import ImagePropertyCol from './image/ImagePropertyCol.vue';

const project = useProjectStore()
const image = computed(() => project.imageList[1])

const imageHeight = computed(() => {
    if(image.value.containerRatio >= 1) {
        return Math.min(400, image.value.height)
    }
})

</script>

<template>
    <Modal :id="ModalId.TEST">
        <template #content>
            <div class="h-100 bg-warning p-2" v-if="image">
                <div class="d-flex h-100">
                    <ImagePropertyCol :image="image" :width="400" :image-height="225" />
                    <div class="flex-grow-1 bg-white h-100">dfdf</div>
                    <div class="bg-info h-100 p-3">fgjfk</div>
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