<script setup lang="ts">
import { ref, shallowRef, onMounted, onUnmounted, watch, computed, toRaw } from 'vue'
import { Colors, greyColor, Instance, MapOptions, PointData } from '@/data/models'
import { useDataStore } from '@/data/stores/dataStore'
import { useMediaStore } from '@/data/stores/mediaStore'
import { useColumnStore } from '@/data/stores/columnStore'
import { generateColors, isTag } from '@/utils/utils'
import { Group } from '@/core/group/types'
import { isNoValue } from '@/core/group/valueParser'
import type { GroupInspector } from '@/core/group/inspector'
import type { ClusterRequest } from '@/core/group/ClusterManager'
import { useMapRenderer } from '@/mixins/mapview/useMapRenderer'
import { imageWorldSize } from '@/mixins/mapview/MapRenderer'
import { cellCenter, DEFAULT_GRID_DENSITY, mapGrid, type MapGrid } from '@/mixins/mapview/GridLayout'
import { konamiMatcher, SnakeGame, type Cell, type SnakeDir, type SnakeState } from '@/mixins/mapview/GridSnake'
import { keyState } from '@/data/composables/keyState'
import { newZoomOwner, zoomModal } from '../modals/zoomModal'
import type { AtlasLoadProgress } from '@/mixins/mapview/AtlasLayerManager'

// Components
import Toolbar from './Toolbar.vue'
import Zoomable from '../Zoomable.vue'
import CenteredImage from '../images/CenteredImage.vue'
import InstanceData from '../data/InstanceData.vue'
import ActionButton2 from '../actions/ActionButton2.vue'
import WithToolTip from '../tooltips/withToolTip.vue'

const DEFAULT_BORDER_WIDTH = 0.05
const DEFAULT_HOVER_SCALE = 2.0
const WHITE_TINT = '#FFFFFF'
const SELECTED_TINT = '#5DACFF'
// Non-members of a focused group go fully desaturated (per-pixel greyscale) rather than a flat
// black/grey wash — that reads as "muted", not "darkened", and is easier on the eye.
const DIM_DESATURATE = 1.0
// z priority tiers, front-to-back: SELECTED > BASE > DIM. Without this, "selected"/"focused" were
// colour-only, and which point actually drew on top of an overlapping neighbour was pure array
// index (AtlasLayer's STACK_Z_RANGE tie-break) — a selected or focused-group point could still
// end up hidden behind an unrelated one. Each tier is spaced well past AtlasLayer's own
// STACK_Z_RANGE (0.1) so index ties never spill into the next tier, and the top tier stays well
// under HDLayer's HD_Z_OFFSET (1.5) so the hover/hover-dot preview still always wins.
const DIM_Z = 0.0
const BASE_Z = 0.5
const SELECTED_Z = 1.0

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

// The group-list island floats over the canvas's right edge — focusGroup needs its on-screen
// footprint to keep framed groups from panning/zooming in behind it.
const groupListIslandRef = ref<HTMLElement | null>(null)

// State
const mouseMode = ref('pan')
const defaultColor = '#777777'

// Border width of the rendered images, adjustable via the header-bar slider. Persisted per view
// through mapOptions (like selectedMap), so the setting survives reloads. Old persisted tabs
// have no borderWidth yet — fall back to the default and fill the field in.
const borderWidth = computed(() => props.mapOptions.borderWidth ?? DEFAULT_BORDER_WIDTH)
// Same story for how much the HD preview grows on hover.
const hoverScale = computed(() => props.mapOptions.hoverScale ?? DEFAULT_HOVER_SCALE)
const layout = computed(() => props.mapOptions.layout ?? 'scatter')
const gridDensity = computed(() => props.mapOptions.gridDensity ?? DEFAULT_GRID_DENSITY)
const fillCells = computed(() => layout.value === 'grid' && !!props.mapOptions.fillCells)
watch(() => props.mapOptions, (opts) => {
    if (opts && opts.borderWidth == null) opts.borderWidth = DEFAULT_BORDER_WIDTH
    if (opts && opts.hoverScale == null) opts.hoverScale = DEFAULT_HOVER_SCALE
    if (opts && opts.layout == null) opts.layout = 'scatter'
    if (opts && opts.gridDensity == null) opts.gridDensity = DEFAULT_GRID_DENSITY
}, { immediate: true })

// The group clicked in the group-list island — its points render at full strength while every
// other point on the map dims out, giving the click a "solo this group" effect. Click the same
// group again (or it disappears from the tree) to go back to showing everything normally.
const selectedGroupId = ref<number | null>(null)
function toggleGroupSelection(leaf: { id: number }) {
    selectedGroupId.value = selectedGroupId.value === leaf.id ? null : leaf.id
}
// Whether the previous updateColors() run had a group soloed — lets updateColors skip the
// position re-upload on ticks where soloing is (and stays) off.
let hadActiveLeaf = false
// Same idea, for whether any image was selected — selection also bumps z (SELECTED_Z) now.
let hadSelected = false

// Last instance the pointer hovered over a point for — kept sticky (only overwritten on a real
// hover, never cleared) so the inspector doesn't blank out the moment the cursor leaves a point.
const lastHoverId = ref<number | null>(null)
watch(hoverInstanceId, (v) => { if (v) lastHoverId.value = v })
const hoverImage = computed<Instance | null>(() => lastHoverId.value != null ? ({ id: lastHoverId.value } as Instance) : null)

// Holding Ctrl over a point opens the full-screen zoom view, like Zoomable does for the
// scrollers' images (keyState.ctrl also covers Option on mac). It follows the hovered point
// and closes on release or once the cursor is off every point.
const zoomOwner = newZoomOwner()
watch([() => keyState.ctrl, hoverInstanceId], ([held, id]) => {
    const ours = zoomModal.open && zoomModal.owner === zoomOwner
    if (held && id != null) {
        if (!zoomModal.open || (ours && zoomModal.image?.id !== id)) {
            zoomModal.show({ id } as Instance, zoomOwner)
        }
    } else if (ours) {
        zoomModal.hide(zoomOwner)
    }
    renderer.value?.setHoverThroughOverlays(zoomModal.open && zoomModal.owner === zoomOwner)
})
onUnmounted(() => zoomModal.hide(zoomOwner))

// The map is keyed by sha1 (one point per sha1); the tree by slot.
let sha1ToPoint: { [sha1: string]: PointData } = {}
// Display leaves of the current tree, with the colour they paint their points with. A ref (not a
// plain let) since the group-list island reads it directly in the template.
const leaves = shallowRef<{ id: number, name: string, color: string, points: PointData[] }[]>([])
const points = shallowRef<PointData[]>([])
// For each slot, the index in `points` of the point drawing it (-1: none). Built with the
// geometry, so a selection tick finds its points with typed-array reads.
let pointOfSlot = new Int32Array(0)
// Each point's z before the selection lifts it: BASE_Z, or DIM_Z while a soloed group dims it.
let baseZ = new Float32Array(0)

// ── Atlas status ──────────────────────────────────────────────────────────────

// Sheet-load progress of the renderer's latest atlas load (null until a load starts).
const atlasLoad = ref<AtlasLoadProgress | null>(null)
// Points on the current map whose sha1 has no atlas cell. The atlas layers skip them, so they
// are not drawn at all — in image mode or point mode.
const mapMissingCount = ref(0)

// Nothing on the map can be drawn: no atlas, or one holding none of the project's images.
// Shown as a message in the middle of the map instead of an empty canvas. Waits for the atlas
// fetch and for the project to have images, so it neither flashes on load nor asks an empty
// project to build an atlas.
const atlasUnusable = computed(() => media.atlasFetched && media.atlasCoverage.total > 0
    && (!media.hasAtlas || media.atlasCoverage.inAtlas === 0))

// Tracks the latest showMap call to cancel stale concurrent invocations
let showMapToken = 0
// Stores args needed to call createMap once the renderer is ready
let pendingCreateMap: { atlas: any; points: PointData[] } | null = null

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
    if (isNoValue(value.value)) return greyColor.color
    return Colors[data.tags[value.value]?.color]?.color ?? fallback
}

function leafName(group: Group, index: number) {
    if (group.name) return group.name
    const value = group.meta?.propertyValues?.[0]
    if (!value) return `Group ${index + 1}`
    const property = data.properties[value.propertyId]
    if (!property) return `Group ${index + 1}`
    if (isTag(property.type)) return !isNoValue(value.value) ? (data.tags[value.value]?.value ?? 'undefined') : 'undefined'
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

    // The tree just rebuilt (regroup, sort, open/close...): if the soloed group's id isn't among
    // the new leaves — regrouping mints new Group objects with new ids — the dim effect would
    // silently do nothing (activeLeaf never found in updateColors). Drop the stale selection
    // instead of leaving the map looking like soloing broke.
    if (selectedGroupId.value != null && !res.some(l => l.id === selectedGroupId.value)) {
        selectedGroupId.value = null
    }

    updateColors()
}

// Full restyle: group borders and solo dimming, then the selection on top.
function updateColors() {
    const pts = points.value
    if (baseZ.length !== pts.length) baseZ = new Float32Array(pts.length)
    for (let i = 0; i < pts.length; i++) {
        const p = pts[i]
        p.color = defaultColor
        p.borderColor = defaultColor
        p.border = 0.0
        p.desaturate = 0.0
        baseZ[i] = BASE_Z
    }

    for (const leaf of leaves.value) {
        for (const point of leaf.points) {
            point.border = borderWidth.value
            point.borderColor = leaf.color
        }
    }

    // Solo a clicked group: dim every point that isn't one of its members, and drop those
    // dimmed points behind so the focused group is never occluded by an overlapping neighbour.
    const activeLeaf = selectedGroupId.value != null
        ? leaves.value.find(l => l.id === selectedGroupId.value)
        : undefined
    if (activeLeaf) {
        const activeSet = new Set(activeLeaf.points)
        for (let i = 0; i < pts.length; i++) {
            const p = pts[i]
            if (!activeSet.has(p)) {
                p.desaturate = DIM_DESATURATE
                baseZ[i] = DIM_Z
                // The leaf-colouring pass above already painted every OTHER leaf's border too —
                // left alone, each dimmed group keeps its own bright border ring around its
                // (now-grey) photos, which is exactly the "still has colour" a solo is meant to
                // remove. Only the focused leaf's border should survive.
                p.border = 0.0
                p.borderColor = defaultColor
            }
        }
    }

    if (renderer.value) {
        renderer.value.updateBorder()
        renderer.value.updateDesaturation()
    }
    // Soloing moves points between z tiers: positions must be re-uploaded while it is or was on.
    updateSelection(!!activeLeaf || hadActiveLeaf)
    hadActiveLeaf = !!activeLeaf
}

// Selection tint and z lift, on top of the style updateColors set. Selection ticks run only this.
//
// A point stands for a whole sha1-pile (possibly several instances, each independently
// selectable in the scrollers — see PileLine.vue), so it is tinted when any slot of its pile is
// selected, matching the pile-wide select/deselect handleLasso does.
function updateSelection(baseZChanged = false) {
    const pts = points.value
    const mask = columnStore.selectionMask(selectNamespace.value)
    const selected = new Uint8Array(pts.length)
    let anySelected = false
    if (mask) {
        const mark = (slot: number) => {
            if (!mask[slot]) return
            const i = pointOfSlot[slot]
            if (i >= 0) { selected[i] = 1; anySelected = true }
        }
        if (builtSlots) for (const slot of builtSlots) mark(slot)
        else for (let slot = 0; slot < pointOfSlot.length; slot++) mark(slot)
    }

    for (let i = 0; i < pts.length; i++) {
        const p = pts[i]
        if (selected[i]) {
            p.tint = SELECTED_TINT
            p.tintAlpha = 0.8
            // Selected always wins the depth tie against an overlapping neighbour, whether or
            // not a group happens to be soloed right now.
            p.z = SELECTED_Z
        } else {
            p.tint = WHITE_TINT
            p.tintAlpha = 0.0
            p.z = baseZ[i] ?? BASE_Z
        }
    }

    if (renderer.value) {
        renderer.value.updateTints()
        // Position upload (re-writes every instance matrix + flags the GPU buffer dirty) only
        // when z can have changed — plain ticks where neither soloing nor any selection is or
        // was active skip this and stay cheap.
        if (baseZChanged || anySelected || hadSelected) renderer.value.updatePosition()
    }
    hadSelected = anySelected
}

// ── Geometry ──────────────────────────────────────────────────────────────────

// Sets x/y for the current layout. The grid spans the whole map (computed once per map), so a
// filtered-out image leaves its cell empty and every image keeps its cell across filters.
function applyLayout(pts: PointData[], mapId: number) {
    const data = media.maps[mapId]?.data
    if (layout.value === 'grid' && data) {
        const grid = mapGrid(toRaw(data), gridDensity.value)
        const size = imageWorldSize(props.imageSize)
        for (const p of pts) [p.x, p.y] = cellCenter(grid, grid.cells.get(p.sha1)!, size)
    } else {
        for (const p of pts) {
            p.x = p.sx
            p.y = p.sy
        }
    }
}

// Re-places the points after a layout or density change, framing the images that were on screen.
function relayout() {
    if (builtMapId == null || !points.value.length) return
    const inView = renderer.value?.getPointsInView() ?? []
    applyLayout(points.value, builtMapId)
    if (!renderer.value) return
    renderer.value.updateLayout(points.value)
    lookAtPoints(inView.length ? inView : points.value)
}

function rescaleGrid(imageSize: number, previous: number) {
    if (layout.value !== 'grid' || builtMapId == null || !points.value.length) return
    applyLayout(points.value, builtMapId)
    if (!renderer.value) return
    renderer.value.updateLayout(points.value)
    renderer.value.scaleCameraPosition(imageWorldSize(imageSize) / imageWorldSize(previous))
    renderSnake()
}

async function showMap(mapId: number, force = false) {
    if (mapId == null || !media.maps[mapId]) return

    const root = props.collection.result?.root
    const slots = root?.slots ?? null
    const fastPath = !force && mapId === builtMapId && root === builtRoot && slots === builtSlots
        && (slots?.length ?? -1) === builtSlotCount
    // Nothing that can move a point changed → recolour only (no GPU re-upload).
    if (fastPath) {
        buildLeaves()
        return
    }

    // Cancel any stale concurrent call
    const token = ++showMapToken
    const mapChanged = mapId !== builtMapId

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
    const sha1ToIndex = new Map<string, number>()
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
            sx: values[i + 1],
            sy: values[i + 2],
            z: BASE_Z,
            color: defaultColor,
            sha1: sha1,
            ratio,
            order: 1,
            border: 0.0,
            tintAlpha: 0.0,
            desaturate: 0.0,
            borderColor: defaultColor
        }
        sha1ToIndex.set(sha1, res.length)
        res.push(p)
        newSha1ToPoint[sha1] = p
    }

    const newPointOfSlot = new Int32Array(columnStore.slotCount()).fill(-1)
    const drawnSlots = slots ?? newPointOfSlot.keys()
    for (const slot of drawnSlots) {
        const sha1 = allSha1s[slot]
        const i = sha1 ? sha1ToIndex.get(sha1) : undefined
        if (i !== undefined) newPointOfSlot[slot] = i
    }

    applyLayout(res, mapId)
    sha1ToPoint = newSha1ToPoint
    pointOfSlot = newPointOfSlot
    points.value = res
    builtMapId = mapId
    builtRoot = root
    builtSlots = slots
    builtSlotCount = slots?.length ?? -1
    buildLeaves()

    const atlas = media.atlas
    if (!atlas) {
        mapMissingCount.value = 0
        atlasLoad.value = null
        return
    }
    let missing = 0
    for (const p of res) if (!atlas.sha1Mapping[p.sha1]) missing++
    mapMissingCount.value = missing

    // If the renderer isn't ready yet, store args so the renderer watcher can call createMap
    if (renderer.value) {
        renderer.value.createMap(atlas, points.value, props.mapOptions.showPoints)
        // The grid's extent depends on the map's size, unlike the projection's fixed range.
        if (mapChanged && layout.value === 'grid') lookAtPoints(res)
    } else {
        pendingCreateMap = { atlas, points: points.value }
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

// Scroll/zoom the camera to frame a group clicked in the group-list island, and solo it the same
// way clicking the group row does — "goto" should land you looking at exactly that group, not a
// group that still needs a second click to stand out from the rest.
function focusGroup(leaf: { id: number, points: PointData[] }) {
    selectedGroupId.value = leaf.id
    lookAtPoints(leaf.points)
}

function lookAtPoints(pts: PointData[]) {
    if (!pts.length) return
    let minX = pts[0].x, minY = pts[0].y, maxX = minX, maxY = minY
    for (const p of pts) {
        minX = Math.min(minX, p.x); minY = Math.min(minY, p.y)
        maxX = Math.max(maxX, p.x); maxY = Math.max(maxY, p.y)
    }
    lookAtBounds({ minX, minY, maxX, maxY })
}

function lookAtBounds(rect: { minX: number, minY: number, maxX: number, maxY: number }) {
    if (!renderer.value) return
    // Reserve the strip the island covers so the framed group doesn't land underneath it.
    const right = islandStrip()
    renderer.value.lookAtRect(rect, right > 0 ? { right } : undefined)
}

// Width of the canvas's right strip covered by the group-list island (its own width plus the gap
// to the canvas's right edge), in CSS px.
function islandStrip() {
    if (!canvasContainer.value || !groupListIslandRef.value) return 0
    const containerRect = canvasContainer.value.getBoundingClientRect()
    const islandRect = groupListIslandRef.value.getBoundingClientRect()
    return Math.max(0, containerRect.right - islandRect.left)
}

// ── Snake easter egg ──────────────────────────────────────────────────────────

// Konami code with the pointer over the map, in grid layout: a snake game over the whole grid
// (its edges are the walls), the camera following the head, the image to eat highlighted in red.
const SNAKE_START_MS = 150
const SNAKE_MIN_MS = 60
const SNAKE_SPEEDUP_MS = 4
const SNAKE_FIRST_STEP_MS = 1200
// Half extent, in cells, of the area framed around the head when a game starts.
const SNAKE_VIEW = { c: 16, r: 11 }
const SNAKE_KEYS: Record<string, SnakeDir> = { ArrowUp: 'up', ArrowDown: 'down', ArrowLeft: 'left', ArrowRight: 'right' }

const snakeState = ref<SnakeState | null>(null)
const snakeScore = ref(0)
const pointerInside = ref(false)
let snake: SnakeGame | null = null
let snakeGrid: MapGrid | null = null
let snakeTimer: number | undefined
const konami = konamiMatcher()

function snakeCellToWorld(c: number, r: number) {
    return cellCenter(snakeGrid!, r * snakeGrid!.cols + c, imageWorldSize(props.imageSize))
}

function renderSnake() {
    if (!snake || !snakeGrid) return
    renderer.value?.snakeLayer.render(snake, snakeCellToWorld, imageWorldSize(props.imageSize))
}

// Camera target: the head, clamped so the view never drifts past the grid's edges — and the grid
// centre on an axis where the whole grid fits on screen.
function followSnake() {
    if (!snake || !snakeGrid || !renderer.value) return
    const size = imageWorldSize(props.imageSize)
    const view = renderer.value.getCameraRect()
    const [hx, hy] = snakeCellToWorld(snake.body[0].c, snake.body[0].r)
    const axis = (head: number, cells: number, viewSpan: number) => {
        const half = cells * size / 2 + size
        const room = half - viewSpan / 2
        return room <= 0 ? 0 : Math.max(-room, Math.min(room, head))
    }
    renderer.value.setFollow({
        x: axis(hx, snakeGrid.cols, view.maxX - view.minX),
        y: axis(hy, snakeGrid.rows, view.maxY - view.minY),
    })
}

function startSnake() {
    const data = builtMapId != null ? media.maps[builtMapId]?.data : null
    if (!data || !renderer.value || !points.value.length) return
    const grid = mapGrid(toRaw(data), gridDensity.value)
    const size = imageWorldSize(props.imageSize)
    const images: Cell[] = []
    for (const p of points.value) {
        const cell = grid.cells.get(p.sha1)
        if (cell != null) images.push({ c: cell % grid.cols, r: Math.floor(cell / grid.cols) })
    }
    const view = renderer.value.getCameraRect()
    const start = {
        c: Math.floor(((view.minX + view.maxX) / 2) / size + grid.cols / 2),
        r: Math.floor(((view.minY + view.maxY) / 2) / size + grid.rows / 2),
    }

    clearTimeout(snakeTimer)
    snakeGrid = grid
    snake = new SnakeGame({ c0: 0, r0: 0, cols: grid.cols, rows: grid.rows }, images, Math.random, start)
    snakeScore.value = 0
    snakeState.value = snake.state
    renderer.value.setHoverEnabled(false)
    renderer.value.setFollow(null)
    renderSnake()
    // Zoom in around the head, never past the grid's edges (a small grid fills the view); the
    // camera then follows the head.
    const head = snake.body[0]
    const [x0, y0] = snakeCellToWorld(Math.max(0, head.c - SNAKE_VIEW.c), Math.max(0, head.r - SNAKE_VIEW.r))
    const [x1, y1] = snakeCellToWorld(Math.min(grid.cols - 1, head.c + SNAKE_VIEW.c), Math.min(grid.rows - 1, head.r + SNAKE_VIEW.r))
    lookAtBounds({ minX: x0, minY: y0, maxX: x1, maxY: y1 })
    // Keep the off-screen arrow clear of the floating toolbar, the HUD and the group-list island.
    renderer.value.snakeLayer.setInsets({ top: 70, bottom: 60, left: 20, right: islandStrip() + 20 })
    snakeTimer = window.setTimeout(snakeTick, SNAKE_FIRST_STEP_MS)
}

function snakeTick() {
    if (!snake) return
    snake.step()
    snakeScore.value = snake.score
    snakeState.value = snake.state
    renderSnake()
    followSnake()
    if (snake.state === 'running') {
        snakeTimer = window.setTimeout(snakeTick, Math.max(SNAKE_MIN_MS, SNAKE_START_MS - snake.score * SNAKE_SPEEDUP_MS))
    }
}

function stopSnake() {
    clearTimeout(snakeTimer)
    if (!snake) return
    snake = null
    snakeGrid = null
    snakeState.value = null
    renderer.value?.snakeLayer.hide()
    renderer.value?.setHoverEnabled(true)
    renderer.value?.setFollow(null)
}

function isTyping(e: KeyboardEvent) {
    const el = e.target as HTMLElement | null
    return !!el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable)
}

function onSnakeKey(e: KeyboardEvent) {
    if (snake) {
        if (e.key === 'Escape') stopSnake()
        else if (e.key === ' ' && snake.state !== 'running') startSnake()
        else if (SNAKE_KEYS[e.key]) snake.turn(SNAKE_KEYS[e.key])
        else return
        e.preventDefault()
        e.stopImmediatePropagation()
        return
    }
    if (layout.value !== 'grid' || !pointerInside.value || isTyping(e)) return
    if (konami(e.key)) startSnake()
}

window.addEventListener('keydown', onSnakeKey, true)
onUnmounted(() => {
    window.removeEventListener('keydown', onSnakeKey, true)
    stopSnake()
})
watch([layout, gridDensity, () => props.mapOptions.selectedMap], stopSnake)

// Watchers
watch(mouseMode, (newMode) => { renderer.value?.setMouseMode(newMode) })
watch(() => columnStore.selectionTick(selectNamespace.value), () => updateSelection())
watch(selectedGroupId, () => updateColors())
watch(() => props.mapOptions.selectedMap, (mapId) => { if (mapId != null) showMap(mapId) })
watch(() => props.mapOptions.showPoints, (val) => renderer.value?.setShowAsPoint(val))
watch(() => props.imageSize, (val, old) => {
    renderer.value?.setImageSize(val)
    rescaleGrid(val, old)
})
watch(layout, relayout)
watch(gridDensity, () => { if (layout.value === 'grid') relayout() })
watch(fillCells, (val) => renderer.value?.setFillCells(val))
watch(borderWidth, () => updateColors())
watch(hoverScale, (val) => renderer.value?.setHoverScale(val))

watch(renderer, (r) => {
    if (r) {
        r.onPointSelection = handleLasso
        r.atlasLayers.onProgress = (p) => { atlasLoad.value = p }
        r.setImageSize(props.imageSize)
        r.setHoverScale(hoverScale.value)
        r.setFillCells(fillCells.value)
        // Flush a createMap call that arrived before the renderer was ready. Read the mode now,
        // not when it was queued: the showPoints watcher had no renderer to reach in between.
        if (pendingCreateMap) {
            r.createMap(pendingCreateMap.atlas, pendingCreateMap.points, props.mapOptions.showPoints)
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
            :images="getRootInstances" :border-width="borderWidth"
            @update:border-width="props.mapOptions.borderWidth = $event" :hover-scale="hoverScale"
            @update:hover-scale="props.mapOptions.hoverScale = $event"
            :grid-density="layout == 'grid' ? gridDensity : null"
            @update:grid-density="props.mapOptions.gridDensity = $event" @delete:map="deleteMap"
            :atlas-load="atlasLoad" :map-missing="mapMissingCount" />

        <div class="map-view-container" @mouseenter="pointerInside = true" @mouseleave="pointerInside = false">
            <div class="map-container"
                :class="{ 'cursor-grab': mouseMode == 'pan', 'cursor-lasso': mouseMode.startsWith('lasso') }">
                <div ref="canvasContainer" class="canvas-wrapper"></div>
            </div>

            <div class="floating-toolbar">
                <WithToolTip message="map.show_points">
                    <div class="tool" :class="{ selected: props.mapOptions.showPoints }"
                        @click="props.mapOptions.showPoints = !props.mapOptions.showPoints">
                        <i class="bi bi-dot"></i>
                    </div>
                </WithToolTip>
                <WithToolTip message="map.grid_layout">
                    <div class="tool" :class="{ selected: layout == 'grid' }"
                        @click="props.mapOptions.layout = layout == 'grid' ? 'scatter' : 'grid'">
                        <i class="bi bi-grid-3x3"></i>
                    </div>
                </WithToolTip>
                <WithToolTip v-if="layout == 'grid'" message="map.fill_cells">
                    <div class="tool" :class="{ selected: fillCells }"
                        @click="props.mapOptions.fillCells = !props.mapOptions.fillCells">
                        <i class="bi bi-aspect-ratio"></i>
                    </div>
                </WithToolTip>
                <WithToolTip message="map.pan">
                    <div class="tool" :class="{ selected: mouseMode == 'pan' }" @click="mouseMode = 'pan'">
                        <i class="bi bi-hand-index-thumb"></i>
                    </div>
                </WithToolTip>
                <WithToolTip message="map.lasso_add">
                    <div class="tool" :class="{ selected: mouseMode == 'lasso-plus' }" @click="mouseMode = 'lasso-plus'">
                        <i class="bi bi-plus-circle-dotted"></i>
                    </div>
                </WithToolTip>
                <WithToolTip message="map.lasso_remove">
                    <div class="tool" :class="{ selected: mouseMode == 'lasso-minus' }" @click="mouseMode = 'lasso-minus'">
                        <i class="bi bi-dash-circle-dotted"></i>
                    </div>
                </WithToolTip>
            </div>

            <div v-if="snakeState" class="snake-hud">
                <i class="bi bi-controller"></i>
                <span class="tabular-nums">{{ $t('map.snake.score', { score: snakeScore }) }}</span>
                <span class="snake-hint">{{ $t('map.snake.' + (snakeState === 'running' ? 'hint' : snakeState)) }}</span>
            </div>

            <div v-if="atlasUnusable" class="atlas-empty">
                <i class="bi bi-grid-3x3-gap atlas-empty-icon"></i>
                <div class="atlas-empty-title">
                    {{ media.hasAtlas ? $t('map.atlas_empty') : $t('map.atlas_none_title') }}
                </div>
                <div class="atlas-empty-text">{{ $t('map.atlas_none') }}</div>
                <template v-if="media.atlasTask">
                    <div class="atlas-empty-progress">
                        <span>{{ $t('map.atlas_generating') }}</span>
                        <span class="tabular-nums">{{ media.atlasTaskPercent }}%</span>
                    </div>
                    <div class="atlas-bar"><div :style="{ width: media.atlasTaskPercent + '%' }"></div></div>
                </template>
                <button v-else class="atlas-generate" :disabled="media.atlasRequested" @click="media.generateAtlas()">
                    {{ media.hasAtlas ? $t('map.atlas_regenerate') : $t('map.atlas_generate') }}
                </button>
            </div>

            <div v-if="hoverImage || leaves.length" ref="groupListIslandRef" class="group-list-island">
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
                        <div v-for="leaf in leaves" :key="leaf.id" class="group-item"
                            :class="{ active: selectedGroupId === leaf.id }" @click="toggleGroupSelection(leaf)">
                            <div class="group-color" :style="{ backgroundColor: leaf.color }"></div>
                            <span class="group-name">{{ leaf.name }}</span>
                            <span class="group-count tabular-nums">{{ leaf.points.length }}</span>
                            <div class="group-actions" @click.stop>
                                <WithToolTip message="btn.goto-group">
                                    <div class="group-action-btn" @click="focusGroup(leaf)">
                                        <i class="bi bi-crosshair"></i>
                                    </div>
                                </WithToolTip>
                                <div class="group-action-btn cluster-btn">
                                    <ActionButton2 action="group" :no-border="true" :defer="true"
                                        :busy="props.collection.isClustering(leaf.id)"
                                        @submit="(req: ClusterRequest) => props.collection.cluster(leaf.id, req)">
                                        <i class="bi bi-intersect"></i>
                                    </ActionButton2>
                                </div>
                            </div>
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

.group-item.active {
    background-color: var(--hover-bg);
    outline: 1px solid var(--primary);
    outline-offset: -1px;
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

.group-actions {
    display: flex;
    align-items: center;
    gap: 2px;
    flex-shrink: 0;
    font-size: 13px;
}

.group-action-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 3px;
    border-radius: var(--radius-sm);
    color: var(--text-tertiary);
    cursor: pointer;
}

.group-action-btn:hover {
    background-color: var(--island-border);
    color: var(--text-primary);
}

.cluster-btn :deep(.b-box) {
    padding: 3px;
    margin: 0;
}

.atlas-empty {
    position: absolute;
    left: 50%;
    top: 50%;
    transform: translate(-50%, -50%);
    z-index: 2;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    width: 280px;
    padding: 20px;
    text-align: center;
    font-size: 13px;
    color: var(--text-primary);
    background: var(--island-surface);
    border: 1px solid var(--island-border);
    border-radius: var(--island-radius);
    box-shadow: var(--island-shadow);
}

.atlas-empty-icon {
    font-size: 24px;
    color: var(--text-tertiary);
}

.atlas-empty-title {
    font-weight: var(--font-weight-semibold);
}

.atlas-empty-text {
    color: var(--text-secondary);
}

.atlas-empty-progress {
    display: flex;
    justify-content: space-between;
    align-self: stretch;
    margin-top: 6px;
    font-size: 12px;
}

.atlas-bar {
    align-self: stretch;
    height: 4px;
    border-radius: 2px;
    background: var(--border-color);
    overflow: hidden;
}

.atlas-bar > div {
    height: 100%;
    background: var(--primary);
    transition: width 0.2s ease;
}

.atlas-generate {
    margin-top: 8px;
    padding: 5px 12px;
    border: none;
    border-radius: var(--radius-sm);
    color: var(--text-inverse);
    background: var(--primary);
    cursor: pointer;
}

.atlas-generate:disabled {
    opacity: 0.6;
    cursor: default;
}

.snake-hud {
    position: absolute;
    left: 50%;
    bottom: 20px;
    transform: translateX(-50%);
    z-index: 2;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 6px 12px;
    font-size: 13px;
    color: var(--text-primary);
    background: var(--island-surface);
    border: 1px solid var(--island-border);
    border-radius: var(--island-radius);
    box-shadow: var(--island-shadow);
}

.snake-hint {
    color: var(--text-secondary);
}

.cursor-grab {
    cursor: grab;
}

.cursor-lasso {
    cursor: crosshair;
}
</style>
