<script setup lang="ts">
import Zoomable from '@/components/Zoomable.vue';
import CenteredImage from '@/components/images/CenteredImage.vue';
import { InstanceEntry } from '@/data/instanceStore';
import { useResizeObserver } from '@vueuse/core';
import { inject, ref } from 'vue';

// The image alone, filling whatever space the open panels leave it.
const props = defineProps<{
    instance: InstanceEntry
    canNavigate: boolean
}>()

const nextImage: () => void = inject('nextImage')
const prevImage: () => void = inject('prevImage')

const elem = ref(null)
const width = ref(0)
const height = ref(0)

useResizeObserver(elem, (entries) => {
    const rect = entries[0].contentRect
    width.value = Math.floor(rect.width)
    height.value = Math.floor(rect.height)
})
</script>

<template>
    <div class="image-area position-relative" ref="elem">
        <Zoomable :image="props.instance" v-if="width > 0 && height > 0">
            <CenteredImage :instance-id="props.instance.id" :width="width" :height="height" no-click />
        </Zoomable>
        <template v-if="props.canNavigate">
            <div class="arrow left" @click="prevImage"><i class="bi bi-arrow-left"></i></div>
            <div class="arrow right" @click="nextImage"><i class="bi bi-arrow-right"></i></div>
        </template>
    </div>
</template>

<style scoped>
.image-area {
    background-color: var(--bg-secondary);
    overflow: hidden;
    /* The image is sized from this box's measured size, so the box must be free to shrink
       when a panel opens — with the default min-height:auto it would stay at its content
       size and the resize observer would never fire again. */
    flex: 1 1 0;
    min-height: 0;
    min-width: 0;
}

.arrow {
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
    font-size: 22px;
    line-height: 22px;
    padding: 6px 8px;
    cursor: pointer;
    border-radius: 50%;
    color: var(--text-secondary);
    background-color: rgba(255, 255, 255, 0.7);
    opacity: 0.5;
}

.arrow:hover {
    opacity: 1;
    color: var(--text-primary);
}

.left {
    left: 10px;
}

.right {
    right: 10px;
}
</style>
