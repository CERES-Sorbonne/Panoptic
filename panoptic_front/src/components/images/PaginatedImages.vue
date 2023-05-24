<script setup lang="ts">
import { Image } from '@/data/models';
import { ref, computed } from 'vue';
import ImageVue from './Image.vue';
import { globalStore } from '@/data/store';

const props = defineProps({
    images: Array<Image>,
    imageSize: { type: Number, default: 100 },
    groupId: String
})

const maxImages = ref(100)
// const pageSize = computed(() => globalStore.settings.pageSize)
const loadedImageCount = computed(() => Math.min(maxImages.value, props.images.length))
const loadedImages = computed(() => props.images.slice(0, loadedImageCount.value))

</script>

<template>
    <div class="d-flex flex-wrap">
        <ImageVue :image="image" :index="index" :size="props.imageSize" v-for="image, index in loadedImages" class="" :groupId="props.groupId" />
    </div>
    <div v-if="loadedImageCount < props.images.length" class="d-flex flex-row mt-1">
        <div class="me-3 text-secondary" style="font-size: 12px;">Afficher plus: </div>
        <div class="me-3"><button class="ps-4 pe-4" @click="maxImages += 20">20</button></div>
        <div class="me-3"><button class="ps-4 pe-4" @click="maxImages += 50">50</button></div>
        <div class="me-3"><button class="ps-4 pe-4" @click="maxImages += 100">100</button></div>
        <div class="me-3"><button class="ps-4 pe-4" @click="maxImages = props.images.length">Voir tout</button></div>
    </div>
</template>
