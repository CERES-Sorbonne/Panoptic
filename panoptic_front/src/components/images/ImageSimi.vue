<script setup lang="ts">
import { computed } from 'vue'
import { useProjectStore } from '@/data/projectStore'
import { Image, ModalId } from '@/data/models';
import { usePanopticStore } from '@/data/panopticStore';
const store = useProjectStore()
const panoptic = usePanopticStore()
const props = defineProps({
    image: Object as () => Image,
    size: { type: Number, default: 100 }
})


const imageSizes = computed(() => {
    let ratio = props.image.width / props.image.height

    let h = props.size
    let w = h * ratio

    if (ratio > 2) {
        w = props.size
        h = props.size / ratio
    }

    return { width: w, height: h }
})

const imageContainerStyle = computed(() => `width: ${imageSizes.value.width - 2}px; height: ${props.size}px;`)
const imageStyle = computed(() => `width: ${imageSizes.value.width - 2}px; height: ${imageSizes.value.height}px;`)
const widthStyle = computed(() => `width: ${Math.max(Number(props.size), imageSizes.value.width)}px;`)

</script>

<template>
    <div class="me-2 mb-2 full-container" :style="widthStyle">
        <div :style="imageContainerStyle" class="img-container" @click="panoptic.showModal(ModalId.IMAGE, props.image)">
            <img :src="props.image.url" :style="imageStyle" />
        </div>
        <div class="text-center text-secondary" style="font-size: 10px;">{{ props.image.dist }}</div>
    </div>
</template>

<style scoped>
.full-container {
    position: relative;
    border: 1px solid var(--border-color);
}

.img-container {
    position: relative;
    margin: auto;
    padding: auto;
    cursor: pointer;
}

.prop-container {
    width: 100%;
    border-top: 1px solid var(--border-color);
    padding: 2px;
    font-size: 12px;
}

img {
    max-height: 100%;
    max-width: 100%;
    /* width: auto;
    height: auto; */
    position: absolute;
    top: 0;
    bottom: 0;
    left: 0;
    right: 0;
    margin: auto;
}
</style>