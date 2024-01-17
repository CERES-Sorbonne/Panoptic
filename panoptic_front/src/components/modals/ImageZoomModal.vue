<script setup lang="ts">
import { Image, ModalId } from '@/data/models';
import Modal from './Modal.vue';
import { usePanopticStore } from '@/data/panopticStore';
import { computed, onMounted, reactive, ref } from 'vue';
import CenteredImage from '../images/CenteredImage.vue';
import { zoomModal } from './zoomModal';


const image = computed(() => zoomModal.image ?? { width: 0, height: 0 } as Image)
const rect = reactive({ width: 500, height: 500 })

onMounted(onWindowResize)
onMounted(() => window.addEventListener('resize', onWindowResize))

function onWindowResize() {
    rect.width = window.innerWidth
    rect.height = window.innerHeight
}


</script>

<template>
    <div v-if="zoomModal.open" class="p-modal">
        <div class="w-100 h-100" v-if="image" >
            <CenteredImage :image="image" :width="rect.width" :height="rect.height" :border="0" />
        </div>
    </div>
</template>

<style scoped>

.p-modal {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: black;
    z-index: 9999;
}

</style>