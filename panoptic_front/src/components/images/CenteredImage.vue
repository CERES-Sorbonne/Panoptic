<script setup lang="ts">
import { Image, Modals } from '@/data/models';
import { globalStore } from '@/data/store';
import { computed } from 'vue';


const props = defineProps({
    image: Object as () => Image,
    width: Number,
    height: Number,
    noClick: Boolean
})

const imageSize = computed(() => {
    let imgRatio = props.image.width / props.image.height
    let divRatio = props.width / props.height

    if (divRatio > imgRatio) {
        return { w: props.height * imgRatio, h: props.height }
    }
    return { w: props.width, h: props.width / imgRatio }

})

const imageUrl = computed(() => {
    let img = props.image
    let minArea = 150 ** 2
    if (props.width * props.height > minArea) {
        return img.fullUrl
    }
    return img.url
})

function openModal() {
    if (props.noClick) return

    globalStore.showModal(Modals.IMAGE, props.image)
}

</script>

<template>
    <div class="image-container" :style="{ width: props.width + 'px', height: props.height + 'px', cursor: props.noClick ? 'inherit': 'pointer' }" @click="openModal">
        <img :src="imageUrl" :style="{ width: imageSize.w + 'px', height: imageSize.h + 'px' }" />
    </div>
</template>

<style scoped>
.image-container {
    text-align: center;
}
</style>