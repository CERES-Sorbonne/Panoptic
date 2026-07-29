<script setup lang="ts">
import { ref, shallowRef, onMounted, watch, computed } from 'vue'
import { Colors, greyColor, Instance, MapOptions, PointData } from '@/data/models'
import { useDataStore } from '@/data/dataStore'
import { useMediaStore } from '@/data/mediaStore'
import { useColumnStore } from '@/data/columnStore'
import { generateColors, isTag } from '@/utils/utils'
import { Group } from '@/core/group/types'
import type { GroupInspector } from '@/core/group/inspector'
import { useMapRenderer } from '@/mixins/mapview/useMapRenderer'

// Components
import Toolbar from './Toolbar.vue'
import Zoomable from '../Zoomable.vue'
import CenteredImage from '../images/CenteredImage.vue'
import InstanceData from '../data/InstanceData.vue'

const BORDER_WIDTH = 0.05
const WHITE_TINT = '#FFFFFF'
const SELECTED_TINT = '#5DACFF'

const data = useDataStore()
const media = useMediaStore()
const columnStore = useColumnStore()

const props = defineProps<{
    // The tree the map renders. Same inspection surface as the scrollers (GroupInspector):
    // membership, colouring and selection all come from it, never from pipeline internals.
    collection: GroupInspector
    // Per-view map display options (Pillar F).
    mapOptions: MapOptions
    // Shared per-view image size (ViewPanel's range input) — the map uses this instead of
    // owning a separate size setting.
    imageSize: number
}>()

const canvasContainer = ref<HTMLElement | null>(null)
const { map: renderer, hoverInstanceId } = useMapRenderer(canvasContainer)

// State
const mouseMode = ref('pan')
const defaultColor = '#777777'

// Last instance the pointer hovered over a point for — kept sticky (only overwritten on a real
// hover, never cleared) so the inspector doesn't blank out the moment the cursor leaves a point.
const lastHoverId = ref<number | null>(null)
watch(hoverInstanceId, (v) => { if (v) lastHoverId.value = v })
const hoverImage = computed<Instance | null>(() => lastHoverId.value != null ? ({ id: lastHoverId.value } as Instance) : null)

// The map is keyed by sha1 (one point per sha1); the tree by slot.
let sha1ToPoint: { [sha1: string]: PointData } = {}
// Display leaves of the current tree, with the colour they paint their points with. A ref (not a
// plain let) since the group-list island reads it directly in the template.
const leaves = shallowRef<{ id: number, name: string, color: string, points: PointData[] }[]>([])
const points = shallowRef<PointData[]>([])

// Tracks the latest showMap call to cancel stale concurrent invocations
let showMapToken = 0
// Stores args needed to call createMap once the renderer is ready
let pendingCreateMap: { atlas: any; points: PointData[]; showAsPoint: boolean } | null = null

// Geometry cache: what the current `points` array was built from. A point can only move when
// the map changes or the root's membership changes — every other tree tick (open/close, sort,
// cluster graft, selection) recolours instead of re-uploading the whole map to the GPU.
let builtMapId: number | null = null
let builtRoot: Group | null = null
let builtSlots: number[] | null = null
// Length too: an incremental add pushes into the SAME root.slots array (GroupManager
// addUpdatedToGroups), so array identity alone would miss new images.
let builtSlotCount = -1

const selectNamespace = computed(() => props.collection.selectionNamespace)

// The collection's current images, for the toolbar's 'map' action. Passed as a getter so it is
// materialised on click only — building an Instance per image on every tree tick is not free.
function getRootInstances(): Instance[] {
    const slots = props.collection.result?.root?.slots ?? []
    const ids = columnStore.instanceIds()
    return slots.map(slot => ({ id: ids[slot] })) as Instance[]
}

// ── Tree reading ──────────────────────────────────────────────────────────────

// The groups the map colours by: the tree's *display* leaves — a group with no children, or a
// closed group standing in for its subtree. This is the same level the scrollers show, so
// opening a group in another pane changes the colouring here too.
function displayLeaves(): Group[] {
    const root = props.collection.result?.root
    if (!root) return []
    const res: Group[] = []
    const walk = (g: Group) => {
        if (!g.children?.length || g.view?.closed) { res.push(g); return }
        for (const c of g.children) walk(c)
    }
    walk(root)
    // The root alone is not a grouping — nothing to colour by.
    return res.length === 1 && res[0] === root ? [] : res
}

function leafColor(group: Group, fallback: string) {
    const value = group.meta?.propertyValues?.[0]
    if (!value) return fallback
    const property = data.properties[value.propertyId]
    if (!property || !isTag(property.type)) return fallback
    if (value.value === undefined) return greyColor.color
    return Colors[data.tags[value.value]?.color]?.color ?? fallback
}

function leafName(group: Group, index: number) {
    if (group.name) return group.name
    const value = group.meta?.propertyValues?.[0]
    if (!value) return `Group ${index + 1}`
    const property = data.properties[value.propertyId]
    if (!property) return `Group ${index + 1}`
    if (isTag(property.type)) return value.value !== undefined ? (data.tags[value.value]?.value ?? 'undefined') : 'undefined'
    return `${property.name}: ${value.value}`
}

// ── Colouring ─────────────────────────────────────────────────────────────────

function buildLeaves() {
    const groups = displayLeaves()
    const sha1s = columnStore.sha1s()
    const colors = generateColors(groups.length)

    const res: { id: number, name: string, color: string, points: PointData[] }[] = []
    groups.forEach((g, index) => {
        const color = leafColor(g, colors[index])
        const seen = new Set<PointData>()
        for (const slot of g.slots ?? []) {
            const point = sha1ToPoint[sha1s[slot]]
            if (point) seen.add(point)
        }
        if (seen.size) res.push({ id: g.id, name: leafName(g, index), color, points: Array.from(seen) })
    })
    leaves.value = res
    updateColors()
}

function updateColors() {
    const ns = selectNamespace.value
    for (const p of points.value) {
        p.color = defaultColor
        p.borderColor = defaultColor
        p.border = 0.0
        p.tint = WHITE_TINT
        p.tintAlpha = 0.0
        p.z = 1.0
    }

    for (const leaf of leaves.value) {
        for (const point of leaf.points) {
            point.border = BORDER_WIDTH
            point.borderColor = leaf.color
        }
    }

    // Selection tint. Read per point instead of materialising the whole selected-id array:
    // this runs on every selection tick.
    for (const p of points.value) {
        if (columnStore.isSelectedId(p.id, ns)) {
            p.tint = SELECTED_TINT
            p.tintAlpha = 0.8
        }
    }

    if (renderer.value) {
        renderer.value.updateBorder()
        renderer.value.updateTints()
    }
}

// ── Geometry ──────────────────────────────────────────────────────────────────

async function showMap(mapId: number, force = false) {
    if (mapId == null || !media.maps[mapId]) return

    const root = props.collection.result?.root
    const slots = root?.slots ?? null
    // Nothing that can move a point changed → recolour only (no GPU re-upload).
    if (!force && mapId === builtMapId && root === builtRoot && slots === builtSlots
        && (slots?.length ?? -1) === builtSlotCount) {
        buildLeaves()
        return
    }

    // Cancel any stale concurrent call
    const token = ++showMapToken

    // Points need real width/height to get their true aspect ratio — the column store only
    // holds a property's data once something requires it (registering a single hovered instance
    // via InstanceData isn't enough to cover every point on the map).
    const widthPropId = data.getSysId('width')
    const heightPropId = data.getSysId('height')
    const loads: Promise<unknown>[] = []
    if (!media.maps[mapId].data) loads.push(media.loadMapData(mapId))
    if (widthPropId !== undefined) loads.push(columnStore.requireFullColumn(widthPropId))
    if (heightPropId !== undefined) loads.push(columnStore.requireFullColumn(heightPropId))
    if (loads.length) await Promise.all(loads)
    if (token !== showMapToken) return

    const values = media.maps[mapId].data
    const allSha1s = columnStore.sha1s()
    const allIds = columnStore.instanceIds()

    // The map draws exactly what the tree holds: the root's slots, mapped to sha1 (one point per
    // sha1, first slot wins). No second membership source — this is the same set the scrollers
    // iterate.
    const sha1ToId: { [sha1: string]: number } = {}
    if (slots?.length) {
        for (let i = 0; i < slots.length; i++) {
            const sha1 = allSha1s[slots[i]]
            if (sha1 && !(sha1 in sha1ToId)) sha1ToId[sha1] = allIds[slots[i]]
        }
    } else {
        for (let s = 0; s < columnStore.slotCount(); s++) {
            const sha1 = allSha1s[s]
            if (sha1 && !(sha1 in sha1ToId)) sha1ToId[sha1] = allIds[s]
        }
    }

    const newSha1ToPoint: { [sha1: string]: PointData } = {}
    const res: PointData[] = []
    for (let i = 0; i < values.length; i += 3) {
        const sha1 = values[i]
        const instanceId = sha1ToId[sha1]
        if (instanceId === undefined || sha1 in newSha1ToPoint) continue

        // `Instance` (data.instances) carries no width/height — those are system columns,
        // read through the column store keyed by instance id.
        const width = data.getSysField(instanceId, 'width')
        const height = data.getSysField(instanceId, 'height')
        const ratio = (width && height) ? width / height : 1

        const p: PointData = {
            id: instanceId,
            x: values[i + 1],
            y: values[i + 2],
            z: 1.0,
            color: defaultColor,
            sha1: sha1,
            ratio,
            order: 1,
            border: 0.0,
            tintAlpha: 0.0,
            borderColor: defaultColor
        }
        res.push(p)
        newSha1ToPoint[sha1] = p
    }

    sha1ToPoint = newSha1ToPoint
    points.value = res
    builtMapId = mapId
    builtRoot = root
    builtSlots = slots
    builtSlotCount = slots?.length ?? -1
    buildLeaves()

    const atlas = media.atlas
    if (!atlas) return

    // If the renderer isn't ready yet, store args so the renderer watcher can call createMap
    if (renderer.value) {
        renderer.value.createMap(atlas, points.value, props.mapOptions.showPoints)
    } else {
        pendingCreateMap = { atlas, points: points.value, showAsPoint: props.mapOptions.showPoints }
    }
}

// ── Actions ───────────────────────────────────────────────────────────────────

const handleLasso = (selectedPoints: PointData[]) => {
    // A point stands for its sha1, so the lasso takes every instance sharing it (sha1-pile rule).
    const ids: number[] = []
    for (const point of selectedPoints) {
        const instanceIds = columnStore.getInstancesBySha1(point.sha1)
        if (instanceIds.length) ids.push(...instanceIds)
    }
    if (mouseMode.value == 'lasso-plus') props.collection.selectImages(ids)
    if (mouseMode.value == 'lasso-minus') props.collection.unselectImages(ids)
}

async function deleteMap(mapId: number) {
    await media.deleteMap(mapId)
}

// Scroll/zoom the camera to frame a group clicked in the group-list island.
function focusGroup(leaf: { points: PointData[] }) {
    if (!renderer.value || !leaf.points.length) return
    let minX = leaf.points[0].x, minY = leaf.points[0].y, maxX = minX, maxY = minY
    for (const p of leaf.points) {
        minX = Math.min(minX, p.x); minY = Math.min(minY, p.y)
        maxX = Math.max(maxX, p.x); maxY = Math.max(maxY, p.y)
    }
    renderer.value.lookAtRect({ minX, minY, maxX, maxY })
}

// Watchers
watch(mouseMode, (newMode) => { renderer.value?.setMouseMode(newMode) })
watch(() => columnStore.selectionTick(selectNamespace.value), () => updateColors())
watch(() => props.mapOptions.selectedMap, (mapId) => { if (mapId != null) showMap(mapId) })
watch(() => props.mapOptions.showPoints, (val) => renderer.value?.setShowAsPoint(val))
watch(() => props.imageSize, (val) => renderer.value?.setImageSize(val))

watch(renderer, (r) => {
    if (r) {
        r.onPointSelection = handleLasso
        r.setImageSize(props.imageSize)
        // Flush a createMap call that arrived before the renderer was ready
        if (pendingCreateMap) {
            r.createMap(pendingCreateMap.atlas, pendingCreateMap.points, pendingCreateMap.showAsPoint)
            pendingCreateMap = null
        } else if (points.value.length > 0 && r.atlasLayers) {
            updateColors()
        }
    }
})

watch(() => media.atlas, () => showMap(props.mapOptions.selectedMap, true))

// React to tree changes via the version tick — geometry is only rebuilt when it can have moved.
watch(() => props.collection.version.value, () => showMap(props.mapOptions.selectedMap))

onMounted(async () => {
    await media.loadMaps()
    showMap(props.mapOptions.selectedMap)
    if (renderer.value) renderer.value.setMouseMode(mouseMode.value)
})
</script>

<template>
    <div class="main-layout">
        <Toolbar :selected-map="props.mapOptions.selectedMap"
            @update:selected-map="id => props.mapOptions.selectedMap = id" :has-maps="media.hasMaps"
            :images="getRootInstances" @delete:map="deleteMap" />

        <div class="map-view-container">
            <div class="map-container"
                :class="{ 'cursor-grab': mouseMode == 'pan', 'cursor-lasso': mouseMode.startsWith('lasso') }">
                <div ref="canvasContainer" class="canvas-wrapper"></div>
            </div>

            <div class="floating-toolbar">
                <div class="tool" :class="{ selected: props.mapOptions.showPoints }"
                    @click="props.mapOptions.showPoints = !props.mapOptions.showPoints" title="Show Points">
                    <i class="bi bi-dot"></i>
                </div>
                <div class="tool" :class="{ selected: mouseMode == 'pan' }" @click="mouseMode = 'pan'" title="Pan">
                    <i class="bi bi-hand-index-thumb"></i>
                </div>
                <div class="tool" :class="{ selected: mouseMode == 'lasso-plus' }" @click="mouseMode = 'lasso-plus'"
                    title="Lasso Add">
                    <i class="bi bi-plus-circle-dotted"></i>
                </div>
                <div class="tool" :class="{ selected: mouseMode == 'lasso-minus' }" @click="mouseMode = 'lasso-minus'"
                    title="Lasso Remove">
                    <i class="bi bi-dash-circle-dotted"></i>
                </div>
            </div>

            <div v-if="hoverImage || leaves.length" class="group-list-island">
                <InstanceData :instance-ids="hoverImage ? [hoverImage.id] : []" :prop-ids="[]">
                    <div v-if="hoverImage" class="group-inspector">
                        <Zoomable :image="hoverImage">
                            <CenteredImage :instance-id="hoverImage.id" :width="190" :height="150" />
                        </Zoomable>
                    </div>
                </InstanceData>


                <template v-if="leaves.length">
                    <div class="group-list-header">
                        <span class="flex-grow-1">{{ $t('map.groups') }}</span>
                        <span>{{ leaves.length }}</span>
                    </div>
                    <div class="group-list-body">
                        <div v-for="leaf in leaves" :key="leaf.id" class="group-item" @click="focusGroup(leaf)">
                            <div class="group-color" :style="{ backgroundColor: leaf.color }"></div>
                            <span class="group-name">{{ leaf.name }}</span>
                            <span class="group-count">{{ leaf.points.length }}</span>
                        </div>
                    </div>
                </template>
            </div>
        </div>
    </div>
</template>

<style scoped>
.main-layout {
    display: flex;
    flex-direction: column;
    height: 100%;
    width: 100%;
    overflow: hidden;
}

.map-view-container {
    display: flex;
    flex-direction: row;
    flex-grow: 1;
    overflow: hidden;
    position: relative;
}

.map-container {
    width: 100%;
    height: 100%;
    z-index: 1;
    position: absolute;
}

.canvas-wrapper {
    width: 100%;
    height: 100%;
    background-color: var(--bg-primary);
}

.floating-toolbar {
    position: absolute;
    left: 50%;
    top: 20px;
    transform: translateX(-50%);
    z-index: 2;
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 4px;
    background: var(--island-surface);
    border: 1px solid var(--island-border);
    border-radius: var(--island-radius);
    box-shadow: var(--island-shadow);
}

.tool {
    color: var(--text-primary);
    line-height: 100%;
    padding: 6px;
    border-radius: var(--radius-sm);
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    justify-content: center;
}

.tool:hover {
    background-color: var(--hover-bg);
}

.selected,
.selected:hover {
    color: var(--text-inverse);
    background-color: var(--primary);
}

.group-list-island {
    position: absolute;
    right: 20px;
    top: 20px;
    max-height: calc(100% - 40px);
    width: 220px;
    z-index: 2;
    display: flex;
    flex-direction: column;
    background: var(--island-surface);
    border: 1px solid var(--island-border);
    border-radius: var(--island-radius);
    box-shadow: var(--island-shadow);
    overflow: hidden;
}

.group-inspector {
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    padding: 10px;
    border-bottom: 1px solid var(--border-color);
}

.group-list-header {
    display: flex;
    align-items: center;
    flex-shrink: 0;
    padding: 8px 10px;
    font-size: 13px;
    font-weight: var(--font-weight-semibold);
    color: var(--text-primary);
    border-bottom: 1px solid var(--border-color);
}

.group-list-body {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 4px;
    flex: 1;
    min-height: 0;
    overflow-y: auto;
}

.group-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px;
    border-radius: var(--radius-sm);
    cursor: pointer;
}

.group-item:hover {
    background-color: var(--hover-bg);
}

.group-color {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    flex-shrink: 0;
}

.group-name {
    flex: 1;
    min-width: 0;
    font-size: 13px;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.group-count {
    font-size: 11px;
    color: var(--text-tertiary);
    flex-shrink: 0;
}

.cursor-grab {
    cursor: grab;
}

.cursor-lasso {
    cursor: crosshair;
}
</style>
