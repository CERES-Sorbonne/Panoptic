<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import type { PointData } from '@/data/models'
import type { MapRenderer } from '@/mixins/mapview/MapRenderer'

const DEFAULT_WIDTH = 200
const MIN_HEIGHT = 60
const MAX_HEIGHT = 200
const MIN_DOT = 1.5
const MAX_DOT = 6
const DIM_COLOR = 'rgba(128, 128, 128, 0.35)'
const DEFAULT_COLOR = '#888888'

const props = defineProps<{
    renderer: MapRenderer | null
    points: PointData[]
    // Bumped by the map whenever points move or restyle in place.
    version: number
    // World size of a thumbnail, used for the dot size and the margin around the map.
    pointSize: number
}>()

const canvasRef = ref<HTMLCanvasElement | null>(null)
const pointsCanvas = document.createElement('canvas')

// World → minimap transform of the last points draw.
let frame = { minX: 0, maxY: 0, scale: 1, offX: 0, offY: 0, width: DEFAULT_WIDTH, height: MIN_HEIGHT }
let pointsDirty = true
let primary = '#5DACFF'
let lastView = ''
let rafId: number | null = null
let dragging = false

function computeFrame() {
    const pts = props.points
    if (!pts.length) return
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
    for (const p of pts) {
        if (p.x < minX) minX = p.x
        if (p.x > maxX) maxX = p.x
        if (p.y < minY) minY = p.y
        if (p.y > maxY) maxY = p.y
    }
    const pad = props.pointSize
    minX -= pad; minY -= pad; maxX += pad; maxY += pad
    const bw = maxX - minX, bh = maxY - minY
    const width = canvasRef.value?.parentElement?.clientWidth || DEFAULT_WIDTH
    const height = Math.round(Math.max(MIN_HEIGHT, Math.min(MAX_HEIGHT, width * bh / bw)))
    const scale = Math.min(width / bw, height / bh)
    frame = {
        minX, maxY, scale, width, height,
        offX: (width - bw * scale) / 2,
        offY: (height - bh * scale) / 2,
    }
}

function drawPoints() {
    computeFrame()
    const dpr = window.devicePixelRatio || 1
    pointsCanvas.width = frame.width * dpr
    pointsCanvas.height = frame.height * dpr
    const ctx = pointsCanvas.getContext('2d')!
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctx.clearRect(0, 0, frame.width, frame.height)

    // Bucketed by style so fillStyle is set once per colour; dimmed first, selected last on top.
    const buckets = new Map<string, { tier: number, color: string, alpha: number, xy: number[] }>()
    for (const p of props.points) {
        let tier = 1, color = p.border && p.borderColor ? p.borderColor : DEFAULT_COLOR
        if (p.tintAlpha > 0) { tier = 2; color = p.tint ?? color }
        else if (p.desaturate) { tier = 0; color = DIM_COLOR }
        const alpha = Math.round((p.opacity ?? 1) * 10) / 10
        const key = `${tier}|${color}|${alpha}`
        let b = buckets.get(key)
        if (!b) buckets.set(key, b = { tier, color, alpha, xy: [] })
        b.xy.push(p.x, p.y)
    }

    const dot = Math.max(MIN_DOT, Math.min(MAX_DOT, props.pointSize * frame.scale))
    const half = dot / 2
    for (const b of [...buckets.values()].sort((a, b) => a.tier - b.tier)) {
        ctx.fillStyle = b.color
        ctx.globalAlpha = b.alpha
        for (let i = 0; i < b.xy.length; i += 2) {
            const [x, y] = toMinimap(b.xy[i], b.xy[i + 1])
            ctx.fillRect(x - half, y - half, dot, dot)
        }
    }
    ctx.globalAlpha = 1
}

function toMinimap(x: number, y: number) {
    return [frame.offX + (x - frame.minX) * frame.scale, frame.offY + (frame.maxY - y) * frame.scale]
}

function toWorld(px: number, py: number) {
    return [frame.minX + (px - frame.offX) / frame.scale, frame.maxY - (py - frame.offY) / frame.scale]
}

function loop() {
    rafId = requestAnimationFrame(loop)
    const canvas = canvasRef.value
    if (!canvas || !props.renderer || !props.points.length) return

    const view = props.renderer.getCameraRect()
    const viewKey = `${view.minX}|${view.maxX}|${view.minY}|${view.maxY}`
    if (!pointsDirty && viewKey === lastView) return
    lastView = viewKey

    if (pointsDirty) {
        drawPoints()
        pointsDirty = false
        primary = getComputedStyle(canvas).getPropertyValue('--primary').trim() || primary
        canvas.width = pointsCanvas.width
        canvas.height = pointsCanvas.height
        canvas.style.width = frame.width + 'px'
        canvas.style.height = frame.height + 'px'
    }

    const dpr = window.devicePixelRatio || 1
    const ctx = canvas.getContext('2d')!
    ctx.setTransform(1, 0, 0, 1, 0, 0)
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    ctx.drawImage(pointsCanvas, 0, 0)
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

    const [x0, y0] = toMinimap(view.minX, view.maxY)
    const [x1, y1] = toMinimap(view.maxX, view.minY)
    ctx.fillStyle = primary
    ctx.globalAlpha = 0.12
    ctx.fillRect(x0, y0, x1 - x0, y1 - y0)
    ctx.globalAlpha = 1
    ctx.strokeStyle = primary
    ctx.lineWidth = 1.5
    ctx.strokeRect(x0, y0, x1 - x0, y1 - y0)
}

function panToPointer(e: PointerEvent) {
    const rect = canvasRef.value!.getBoundingClientRect()
    const [x, y] = toWorld(e.clientX - rect.left, e.clientY - rect.top)
    props.renderer?.centerOn(x, y)
}

function onPointerDown(e: PointerEvent) {
    if (e.button !== 0) return
    dragging = true
    canvasRef.value?.setPointerCapture(e.pointerId)
    panToPointer(e)
}

function onPointerMove(e: PointerEvent) {
    if (dragging) panToPointer(e)
}

function onPointerUp(e: PointerEvent) {
    dragging = false
    canvasRef.value?.releasePointerCapture(e.pointerId)
}

function markDirty() {
    pointsDirty = true
}

watch(() => [props.points, props.version, props.pointSize], markDirty)

onMounted(() => loop())
onUnmounted(() => { if (rafId != null) cancelAnimationFrame(rafId) })
</script>

<template>
    <canvas ref="canvasRef" class="minimap-canvas" @pointerdown="onPointerDown" @pointermove="onPointerMove"
        @pointerup="onPointerUp" @pointercancel="onPointerUp"></canvas>
</template>

<style scoped>
.minimap-canvas {
    display: block;
    flex-shrink: 0;
    cursor: pointer;
    user-select: none;
}
</style>
