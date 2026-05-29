<script setup lang="ts">
import { SERVER_PREFIX } from '@/data/apiPanopticRoutes'
import { usePanopticStore } from '@/data/panopticStore'
import { useDataStore } from '@/data/dataStore'
import { computed, ref, watch, onUnmounted } from 'vue'
import { useInstanceStore } from '@/data/instanceStore';

const props = defineProps<{
    instanceId:  number
    width:       number
    height:      number
    noClick?:    boolean
    border?:     number
    isZoom?:     boolean
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

function buildUrl(s: string): string {
    const projectId = panoptic.connectionState?.connectedProject
    const size      = Math.ceil(Math.max(props.width, props.height))
    return `${SERVER_PREFIX}/projects/${projectId}/image/by_size/${s}?size=${size}`
}

watch(sha1, (s) => {
    if (loadTimer) clearTimeout(loadTimer)
    activeUrl.value = ''
    loadedUrl.value = null
    if (!s) return
    loadTimer = setTimeout(() => {
        activeUrl.value = buildUrl(s)
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
    if (divRatio > imgRatio) return { w: props.height * imgRatio, h: props.height }
    return { w: props.width, h: props.width / imgRatio }
})

const loadedImageUrl = computed(() => loadedUrl.value)

function onLoad() {
    loadedUrl.value = activeUrl.value
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
