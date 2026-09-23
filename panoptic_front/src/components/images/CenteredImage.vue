<script lang="ts">
// Module-level cache of URLs that have already loaded at least once (and are therefore in
// the browser's HTTP cache). Lets a freshly-mounted/recycled cell show the image instantly
// instead of blanking while it reloads — the main source of flicker during live updates.
const loadedUrlCache = new Set<string>()
</script>

<script setup lang="ts">
import { SERVER_PREFIX } from '@/data/api/panopticApi'
import { usePanopticStore } from '@/data/stores/panopticStore'
import { useDataStore } from '@/data/stores/dataStore'
import { computed, ref, watch, onUnmounted } from 'vue'
import { useInstanceStore } from '@/data/stores/instanceStore';

const props = defineProps<{
    instanceId:  number
    width:       number
    height:      number
    noClick?:    boolean
    border?:     number
    isZoom?:     boolean
    // Fill the whole box instead of fitting inside it: the image is scaled up until it covers
    // width AND height, and the overflow is cropped (centred, so it crops evenly on both sides).
    cover?:      boolean
}>()

const panoptic   = usePanopticStore()
const data       = useDataStore()
const instanceStore = useInstanceStore()
const loadedUrl  = ref<string | null>(null)
const activeUrl  = ref('')
let loadTimer: ReturnType<typeof setTimeout> | null = null

const sha1 = computed(() => instanceStore.instanceData[props.instanceId]?.sha1 as string | undefined)
const imageWidth  = computed(() => instanceStore.instanceData[props.instanceId]?.width  as number | undefined)
const imageHeight = computed(() => instanceStore.instanceData[props.instanceId]?.height as number | undefined)

// Size asked from the server, rounded up to a power of two. The server only stores a few
// sizes (128/256/1024...), so this picks the same one, and gives an image the same URL in
// cells a pixel apart (browser cache hits).
const requestSize = computed(() => {
    const px = Math.max(props.width || 0, props.height || 0, 128)
    return 2 ** Math.ceil(Math.log2(px))
})

function buildUrl(s: string, size: number): string {
    const projectId = panoptic.connectionState?.connectedProject
    return `${SERVER_PREFIX}/projects/${projectId}/image/by_size/${s}?size=${size}`
}

// The image shown (or loading) and the size it was asked at.
let shownSha1: string | undefined
let shownSize = 0

watch([sha1, requestSize], ([s, size]) => {
    if (!s) {
        // No image for this instance → clear.
        if (loadTimer) clearTimeout(loadTimer)
        activeUrl.value = ''
        loadedUrl.value = null
        shownSha1 = undefined
        shownSize = 0
        return
    }
    if (s === shownSha1) {
        // Same image in a box that changed size. A smaller box keeps what it has; a
        // bigger one loads the sharper version behind the current image (the hidden
        // <img>), which stays visible until onLoad swaps it.
        if (size <= shownSize) return
        shownSize = size
        if (loadTimer) clearTimeout(loadTimer)
        loadTimer = null
        const url = buildUrl(s, size)
        activeUrl.value = url
        if (loadedUrlCache.has(url)) loadedUrl.value = url
        return
    }
    if (loadTimer) clearTimeout(loadTimer)
    shownSha1 = s
    shownSize = size
    const url = buildUrl(s, size)
    if (loadedUrlCache.has(url)) {
        // Loaded before (in browser cache) → show instantly, no white frame. This is what
        // keeps an UNCHANGED image from flickering when the cell remounts/recycles.
        activeUrl.value = url
        loadedUrl.value = url
        return
    }
    // Genuinely new image → go white instantly, then load it in.
    activeUrl.value = ''
    loadedUrl.value = null
    loadTimer = setTimeout(() => {
        activeUrl.value = url
        loadTimer = null
    }, 20)
}, { immediate: true })

onUnmounted(() => {
    if (loadTimer) clearTimeout(loadTimer)
    activeUrl.value = ''
})

const imageSize = computed(() => {
    if (!imageWidth.value || !imageHeight.value) return { w: 0, h: 0 }
    const imgRatio = imageWidth.value / imageHeight.value
    const divRatio = props.width / props.height
    // cover: scale on the axis that still leaves a gap, so the image overflows the other one
    // (cropped by the container) — the exact mirror of the fit case below.
    if (props.cover) {
        if (divRatio > imgRatio) return { w: props.width, h: props.width / imgRatio }
        return { w: props.height * imgRatio, h: props.height }
    }
    if (divRatio > imgRatio) return { w: props.height * imgRatio, h: props.height }
    return { w: props.width, h: props.width / imgRatio }
})

const loadedImageUrl = computed(() => loadedUrl.value)

function onLoad() {
    if (!activeUrl.value) return
    loadedUrl.value = activeUrl.value
    loadedUrlCache.add(activeUrl.value)
}
</script>

<template>
    <div class="center-container" :class="{ 'cover-crop': props.cover }"
        :style="{ width: props.width + 'px', height: props.height + 'px', cursor: props.noClick ? 'inherit' : 'pointer' }">
        <div class="center-content">
            <img v-if="loadedImageUrl" :src="loadedImageUrl"
                :style="{ width: imageSize.w + 'px', height: imageSize.h + 'px', border: props.border > 0 ? (props.border + 'px solid var(--border-color)') : 'none', borderRadius: props.border > 0 ? '3px' : '' }"
                @load="onLoad">
            <img style="opacity: 0; position: absolute; width: 0; height: 0;" :src="activeUrl" @load="onLoad" />
        </div>
    </div>
</template>

<style scoped>
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

/* Cover mode: the image is deliberately larger than the box on one axis, so the box must clip
   it and the fit-mode max-width clamp must not shrink it back. Centred, so it crops evenly. */
.cover-crop {
    overflow: hidden;
}

.cover-crop img {
    max-width: none;
}

img {
    max-width: 100%;
    height: auto;
    vertical-align: middle;
}
</style>
