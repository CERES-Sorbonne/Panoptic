<script setup lang="ts">
import { computed } from 'vue'
import { globalStore } from '@/data/store';
import { Image, Modals } from '@/data/models';

const props = defineProps({
    image: Object as () => Image,
    size: { type: Number, default: 100 },
    callback: {type: Function},
    refuse: {type: Function}
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
        <div :style="imageContainerStyle" class="img-container" @click="globalStore.showModal(Modals.IMAGE, props.image)">
            <img :src="props.image.url" :style="imageStyle" />
        </div>
        <div class="row">
            <div class="col">
                <div class="text-center text-success clickable bouton" style="font-size: 10px;" @click="props.callback(image.sha1)"> ✓ </div>
            </div>
            <div class="col">
                <div class="text-center text-danger clickable bouton" style="font-size: 10px;" @click="props.refuse(image.sha1)"> ✕ </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.bouton:hover{
    background-color: lightsteelblue;
}

.bouton{
    padding: 0.5rem
}
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