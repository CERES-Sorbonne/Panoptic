<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import CenteredImage from '../images/CenteredImage.vue';
import { zoomModal } from './zoomModal';
import { Instance } from '@/data/models';


const image = computed(() => zoomModal.image ?? { width: 0, height: 0 } as Instance)
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
        <div class="w-100 h-100" v-if="image" style="padding: 28px;">
            <CenteredImage :image="image" :width="rect.width - 56" :height="rect.height - 56" :border="4" :is-zoom="true" />
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
    background-color: rgba(0, 0, 0, 0.77);
    z-index: 9999;
}
</style>
