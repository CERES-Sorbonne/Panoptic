<script setup lang="ts">
import { Image } from '@/data/models';
import { ref, computed } from 'vue';
import ImageVue from './Image.vue';
import { globalStore } from '@/data/store';

const props = defineProps({
    images: Array<Image>,
    imageSize: { type: String, default: '150' },
})

const loadedPages = ref(1)

const pageSize = computed(() => globalStore.settings.pageSize)
const loadedImageCount = computed(() => Math.min(loadedPages.value * pageSize.value, props.images.length))
const loadedImages = computed(() => props.images.slice(0, loadedImageCount.value))

</script>

<template>
    <ImageVue :image="image" :index="index" :width="props.imageSize" v-for="image, index in loadedImages" class=""/>
    <div v-if="loadedImageCount < props.images.length" class="d-inline-block overflow-hidden align-items-center" :style="`width: ${props.imageSize}px; height: ${props.imageSize}px;`">
        <div class="d-flex justify-content-center align-items-center h-100 w-100">
            <button @click="loadedPages += 1" class="btn btn-primary">More..<br/>({{ props.images.length - loadedImageCount }})</button>
    </div>
    </div>
</template>
