<script setup lang="ts">
import { Instance } from '@/data/models';
import { computed, ref } from 'vue';

const props = defineProps<{
    image: Instance
    width: number,
    height: number,
    noClick?: boolean,
    border?: number,
    isZoom?: boolean
}>()

const hover = ref(false)
const imageElem = ref(null)
const invisible = ref(false)
const loadedImage = ref(null)

const imageSize = computed(() => {
    if (!props.image) {
        return { w: 0, h: 0 }
    }
    let imgRatio = props.image.width / props.image.height
    let divRatio = props.width / props.height

    if (divRatio > imgRatio) {
        return { w: props.height * imgRatio, h: props.height }
    }
    return { w: props.width, h: props.width / imgRatio }

})

const imageUrl = computed(() => {
    let img = props.image
    const size = Math.max(props.width, props.height)

    if(size < 150) return img.urlSmall
    if(size < 300) return img.urlMedium
    if(size < 1024) return img.urlLarge
    return img.urlRaw
})

const loadedImageUrl = computed(() => {
    let img = loadedImage.value
    if (!img) return

    const size = Math.max(props.width, props.height)

    if(size < 150) return img.urlSmall
    if(size < 300) return img.urlMedium
    if(size < 1024) return img.urlLarge
    return img.urlRaw
})

function onLoad() {
    loadedImage.value = props.image
}
</script>

<template>
    <div class="center-container" @mouseenter="hover = true" @mouseleave="hover = false" ref="imageElem"
        :style="{ width: props.width + 'px', height: props.height + 'px', cursor: props.noClick ? 'inherit' : 'pointer' }">
        <div class="center-content">
            <img v-if="!invisible && loadedImageUrl" :src="loadedImageUrl"
                :style="{ width: imageSize.w + 'px', height: imageSize.h + 'px', border: props.border > 0 ? (props.border + 'px solid var(--border-color)') : 'none', borderRadius: props.border > 0 ? '3px' : '' }"
                @load="onLoad">
            <img style="opacity: 0; position: absolute; width: 0; height: 0;" :src="imageUrl" @load="onLoad" />
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