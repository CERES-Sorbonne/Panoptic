<script setup lang="ts">
import { Image, ModalId } from '@/data/models';
import { usePanopticStore } from '@/data/panopticStore';
import { useProjectStore } from '@/data/projectStore'
import { computed } from 'vue';
const store = useProjectStore()

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
    const panoptic = usePanopticStore()
    panoptic.showModal(ModalId.IMAGE, props.image)
}

</script>

<template>
    <!-- <div class="image-container"
        :style="{ width: props.width + 'px', height: props.height + 'px', cursor: props.noClick ? 'inherit' : 'pointer' }"
        @click="openModal">
        <template v-if="props.shadow">
            <div class="box-shadow" :style="{ width: props.width + 'px', height: '3px' }">
                <img :src="imageUrl" :style="{ width: imageSize.w + 'px', height: imageSize.h + 'px' }" />
            </div>
        </template>
        <template v-else>
            <img :src="imageUrl" :style="{ width: imageSize.w + 'px', height: imageSize.h + 'px' }" />
        </template>

    </div> -->

    <div class="center-container"
        :style="{ width: props.width + 'px', height: props.height + 'px', cursor: props.noClick ? 'inherit' : 'pointer' }"
        @click="openModal">
        <div class="center-content">
            <img :src="imageUrl" :style="{ width: imageSize.w + 'px', height: imageSize.h + 'px' }">
        </div>
    </div>
</template>

<style scoped>
.other {
    height: 100vh;
}

.center-container {
    text-align: center;
    margin: 0;
    display: flex;
    align-items: center;
    justify-content: center;
}

.center-content {
    margin: 0;
    padding: 0;
    display: inline-block;
}

img {
    max-width: 100%;
    height: auto;
    vertical-align: middle;
}

.image-container {
    text-align: center;
    background-color: white;
    position: relative;
    /* border: 1px solid var(--border-color); */
}


.box-shadow {
    position: relative;
}

.box-shadow::after {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    -webkit-box-shadow: inset 0 0 10px 10px #000;
    -moz-box-shadow: inset 0 0 10px 10px #000;
    box-shadow: inset 0px 2px 3px var(--border-color);
    overflow: hidden;
}
</style>