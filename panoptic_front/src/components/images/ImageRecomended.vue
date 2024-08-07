<script setup lang="ts">
import { computed } from 'vue'
import { ModalId } from '@/data/models';
import wTT from '../tooltips/withToolTip.vue'
import { Group } from '@/core/GroupManager';
import { usePanopticStore } from '@/data/panopticStore';
import Zoomable from '../Zoomable.vue';
import CenteredImage from './CenteredImage.vue';
const panoptic = usePanopticStore()
const props = defineProps({
    pile: Object as () => Group,
    size: { type: Number, default: 100 },
})

const emits = defineEmits(['accept', 'refuse'])

const imageContainerStyle = computed(() => `width: ${props.size}px; height: ${props.size}px;`)
const imageStyle = computed(() => `max-width: ${props.size - 2}px; max-height: ${props.size - 1}px;`)
const image = computed(() => props.pile.images[0])

</script>

<template>
    <div class="">
        <Zoomable :image="image">
            <div :style="imageContainerStyle" class="img-container" @click="panoptic.showModal(ModalId.IMAGE, { image })">
                <!-- <div class="image-count" v-if="props.pile.images.length > 1">{{ props.pile.images.length }}</div> -->
                <!-- <img :src="image.url" :style="imageStyle" /> -->
                 <CenteredImage :image="image" :width="props.size-2" :height="props.size-1" />
            </div>
        </Zoomable>
        <div class="d-flex flex-row">
            <wTT message="main.recommand.accept">
                <div :style="'width: ' + ((props.size / 2)) + 'px;'"
                    class="text-center text-success validate clickable unselectable" style="font-size: 10px;"
                    @click="emits('accept', image)"> ✓ </div>
            </wTT>
            <wTT message="main.recommand.refuse">
                <div :style="'width: ' + ((props.size / 2)) + 'px;'"
                    class="text-center text-danger refuse clickable unselectable" style="font-size: 10px;"
                    @click="emits('refuse', image)"> ✕ </div>
            </wTT>
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

.refuse:hover {
    background-color: var(--refuse-border);
}

.validate:hover {
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
}</style>