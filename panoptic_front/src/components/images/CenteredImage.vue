<script setup lang="ts">
import { SERVER_PREFIX } from '@/data/apiPanopticRoutes'
import { usePanopticStore } from '@/data/panopticStore'
import { computed, ref, watch, onUnmounted } from 'vue'

const props = defineProps<{
    sha1?:        string
    imageWidth?:  number
    imageHeight?: number
    width:        number
    height:       number
    noClick?:     boolean
    border?:      number
    isZoom?:      boolean
}>()

const panoptic   = usePanopticStore()
const loadedSha1 = ref<string | null>(null)
const activeUrl  = ref('')
let loadTimer: ReturnType<typeof setTimeout> | null = null

function buildUrl(sha1: string): string {
    const projectId = panoptic.connectionState?.connectedProject
    const size      = Math.ceil(Math.max(props.width, props.height))
    return `${SERVER_PREFIX}/projects/${projectId}/image/by_size/${sha1}?size=${size}`
}

watch(() => props.sha1, (sha1) => {
    if (loadTimer) clearTimeout(loadTimer)
    activeUrl.value = ''
    loadedSha1.value = null
    if (!sha1) return
    loadTimer = setTimeout(() => {
        activeUrl.value = buildUrl(sha1)
        loadTimer = null
    }, 20)
}, { immediate: true })

onUnmounted(() => {
    if (loadTimer) clearTimeout(loadTimer)
    activeUrl.value = ''
})

const imageSize = computed(() => {
    if (!props.imageWidth || !props.imageHeight) return { w: 0, h: 0 }
    const imgRatio = props.imageWidth / props.imageHeight
    const divRatio = props.width / props.height
    if (divRatio > imgRatio) return { w: props.height * imgRatio, h: props.height }
    return { w: props.width, h: props.width / imgRatio }
})

const loadedImageUrl = computed(() => loadedSha1.value ? buildUrl(loadedSha1.value) : null)

function onLoad() {
    loadedSha1.value = props.sha1
}
</script>

<template>
    <div class="center-container"
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

img {
    max-width: 100%;
    height: auto;
    vertical-align: middle;
}
</style>
