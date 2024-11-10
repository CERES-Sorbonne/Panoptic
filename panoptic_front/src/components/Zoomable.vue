<script setup lang="ts">
import { keyState } from '@/data/keyState';
import { ref, watch } from 'vue';
import { zoomModal } from './modals/zoomModal';
import { Instance } from '@/data/models';

const props = defineProps<{
    image: Instance
}>()

const hover = ref(false)
const elem = ref(null)

watch(keyState, () => {
    const isActive = zoomModal.open && zoomModal.image.id === props.image.id
    const isHover = hover.value
    if (!isActive && !isHover) return

    if (isHover && !isActive && keyState.ctrl) {
        zoomModal.show(props.image)
    }

    const rect = elem.value.getBoundingClientRect()
    const absoluteHover = keyState.mouseX >= rect.x && keyState.mouseX <= rect.right && keyState.mouseY >= rect.y && keyState.mouseY <= rect.bottom
    
    if (isActive && (!absoluteHover || !keyState.ctrl)) {
        zoomModal.hide()
    }
})
</script>

<template>
    <div @mouseenter="hover = true" @mouseleave="hover = false" ref="elem">
        <slot></slot>
    </div>
</template>