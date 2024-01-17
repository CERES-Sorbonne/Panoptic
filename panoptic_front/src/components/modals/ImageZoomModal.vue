<script setup lang="ts">
import { Image, ModalId } from '@/data/models';
import Modal from './Modal.vue';
import { usePanopticStore } from '@/data/panopticStore';
import { computed, ref } from 'vue';
import CenteredImage from '../images/CenteredImage.vue';

const panoptic = usePanopticStore()

const image = computed(() => panoptic.modalData ?? {width: 0, height: 0} as Image)
const rect = ref({ width: 0, height: 0})

function onShow() {
}

function onHide() {
}

</script>

<template>
    <Modal :id="ModalId.IMAGE_ZOOM" @show="onShow" @hide="onHide" :no-title="true" @resize="e => rect = e">
        <template #content="{ data }">
            <div class="w-100 h-100" v-if="image">
               <CenteredImage :image="image" :width="rect.width-56" :height="rect.height-56" />
            </div>
        </template>
    </Modal>
</template>

<style scoped>

img {
    max-width: 100%;
    max-height: 100%;
}
</style>