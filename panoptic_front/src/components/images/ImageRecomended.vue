<script setup lang="ts">
import { computed } from 'vue'
import { globalStore } from '@/data/store';
import { Image, Modals } from '@/data/models';

const props = defineProps({
    image: Object as () => Image,
    size: { type: Number, default: 100 },
})

const emits = defineEmits(['accept', 'refuse'])

const imageContainerStyle = computed(() => `width: ${props.size}px; height: ${props.size}px;`)
const imageStyle = computed(() => `max-width: ${props.size - 2}px; max-height: ${props.size -1}px;`)

</script>

<template>
    <div class="">
        <div :style="imageContainerStyle" class="img-container" @click="globalStore.showModal(Modals.IMAGE, props.image)">
            <img :src="props.image.url" :style="imageStyle" />
        </div>
        <div class="d-flex flex-row">
            <div :style="'width: ' + ((props.size / 2)) + 'px;'" class="text-center text-success validate clickable unselectable" style="font-size: 10px;" @click="emits('accept', props.image)"> ✓ </div>
            <div :style="'width: ' + ((props.size / 2)) + 'px;'" class="text-center text-danger refuse clickable unselectable" style="font-size: 10px;" @click="emits('refuse', props.image)"> ✕ </div>
        </div>
    </div>
</template>

<style scoped>
.validate {
    padding: 3px;
    border: 1px solid var(--validate-border);
}

.refuse {
    padding: 3px;
    border: 1px solid var(--refuse-border);
}

.refuse:hover{
    background-color: var(--refuse-border);
}

.validate:hover{
    background-color: var(--validate-border);
}

.img-container {
    position: relative;
    margin: auto;
    padding: auto;
    cursor: pointer;
    border-top: 1px solid var(--border-color);
    border-left: 1px solid var(--border-color);
    border-right: 1px solid var(--border-color);
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