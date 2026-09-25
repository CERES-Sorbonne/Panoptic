<script setup lang="ts">
import { keyState } from '@/data/composables/keyState';
import { onUnmounted, ref, watch } from 'vue';
import { newZoomOwner, zoomModal } from './modals/zoomModal';
import { Instance } from '@/data/models';

const props = defineProps<{
    image: Instance
}>()

// Identifies this component, not its image: see zoomModal.owner.
const id = newZoomOwner()
const hover = ref(false)
const elem = ref(null)

function isMouseInside() {
    const rect = elem.value?.getBoundingClientRect()
    if (!rect) return false
    return keyState.mouseX >= rect.x && keyState.mouseX <= rect.right && keyState.mouseY >= rect.y && keyState.mouseY <= rect.bottom
}

watch([() => keyState.ctrl, () => keyState.mouseX, () => keyState.mouseY], () => {
    const isActive = zoomModal.open && zoomModal.owner === id
    if (!isActive) {
        // `hover` can be stale (a recycled line moved away without a mouseleave), so the
        // cursor position has the last word.
        if (!zoomModal.open && hover.value && keyState.ctrl && isMouseInside()) {
            zoomModal.show(props.image, id)
        }
        return
    }

    const inside = isMouseInside()
    if (!inside || !keyState.ctrl) {
        zoomModal.hide(id)
        // The modal covered this element, so its mouseleave already fired. Set the hover
        // back from the cursor, or pressing Ctrl again without moving would do nothing.
        hover.value = inside
    }
})

// A recycled scroller line can hand this component another image while it owns the modal.
watch(() => props.image, (image) => {
    if (zoomModal.open && zoomModal.owner === id) zoomModal.show(image, id)
})

onUnmounted(() => zoomModal.hide(id))
</script>

<template>
    <div @mouseenter="hover = true" @mouseleave="hover = false" ref="elem">
        <slot></slot>
    </div>
</template>
