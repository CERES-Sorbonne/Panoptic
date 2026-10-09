<script lang="ts">
import { keyState } from '@/data/composables/keyState';
import { effectScope, onMounted, onUnmounted, ref, watch } from 'vue';
import { newZoomOwner, zoomModal } from './modals/zoomModal';
import { Instance } from '@/data/models';

// Module scope, shared by every Zoomable. A scroller mounts one per card, and each used to watch
// Ctrl and the mouse position itself: every mousemove then ran one callback per card on screen,
// for at most one of them to act. One watcher now serves them all, and only looks at the cards
// the pointer has entered.
interface ZoomTarget {
    // Identifies the component, not its image: see zoomModal.owner.
    id: number
    elem: () => HTMLElement | null
    image: () => Instance
}

const targets = new Map<number, ZoomTarget>()
// The targets whose mouseenter fired without their mouseleave. Usually one; a recycled line can
// leave a stale one behind, which the cursor test below rules out.
const hovered = new Set<ZoomTarget>()
let stopWatching: (() => void) | undefined

function setHover(target: ZoomTarget, on: boolean) {
    if (on) hovered.add(target)
    else hovered.delete(target)
}

function isMouseInside(target: ZoomTarget) {
    const rect = target.elem()?.getBoundingClientRect()
    if (!rect) return false
    return keyState.mouseX >= rect.x && keyState.mouseX <= rect.right && keyState.mouseY >= rect.y && keyState.mouseY <= rect.bottom
}

function onPointerOrCtrl() {
    if (zoomModal.open) {
        // Only the Zoomable that opened the modal may close it; an owner that is not one of
        // ours (the map view) is none of our business.
        const owner = zoomModal.owner === null ? undefined : targets.get(zoomModal.owner)
        if (!owner) return
        const inside = isMouseInside(owner)
        if (!inside || !keyState.ctrl) {
            zoomModal.hide(owner.id)
            // The modal covered this element, so its mouseleave already fired. Set the hover
            // back from the cursor, or pressing Ctrl again without moving would do nothing.
            setHover(owner, inside)
        }
        return
    }

    if (!keyState.ctrl) return
    // The hover flag can be stale (a recycled line moved away without a mouseleave), so the
    // cursor position has the last word.
    for (const target of hovered) {
        if (isMouseInside(target)) {
            zoomModal.show(target.image(), target.id)
            return
        }
    }
}

function register(target: ZoomTarget) {
    targets.set(target.id, target)
    if (stopWatching) return
    // Detached scope: the watcher belongs to no component, so it outlives whichever Zoomable
    // happened to start it, and stops when the last one goes.
    const scope = effectScope(true)
    scope.run(() => watch([() => keyState.ctrl, () => keyState.mouseX, () => keyState.mouseY], onPointerOrCtrl))
    stopWatching = () => scope.stop()
}

function unregister(target: ZoomTarget) {
    targets.delete(target.id)
    hovered.delete(target)
    zoomModal.hide(target.id)
    if (targets.size || !stopWatching) return
    stopWatching()
    stopWatching = undefined
}
</script>

<script setup lang="ts">
const props = defineProps<{
    image: Instance
}>()

const elem = ref<HTMLElement | null>(null)
const target: ZoomTarget = {
    id: newZoomOwner(),
    elem: () => elem.value,
    image: () => props.image,
}

onMounted(() => register(target))
onUnmounted(() => unregister(target))

// A recycled scroller line can hand this component another image while it owns the modal.
watch(() => props.image, (image) => {
    if (zoomModal.open && zoomModal.owner === target.id) zoomModal.show(image, target.id)
})
</script>

<template>
    <div @mouseenter="setHover(target, true)" @mouseleave="setHover(target, false)" ref="elem">
        <slot></slot>
    </div>
</template>
