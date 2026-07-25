<script setup lang="ts">
import { ref, shallowRef, onMounted, watch, computed, onUnmounted, nextTick } from 'vue'
import { Colors, greyColor, Instance, MapGroup, MapOptions, PointData } from '@/data/models'
import { useDataStore } from '@/data/dataStore'
import { useMediaStore } from '@/data/mediaStore'
import { useColumnStore } from '@/data/columnStore'
import { TabManager } from '@/core/TabManager'
import { CollectionManager } from '@/core/CollectionManager'
import { generateColors, isTag, sleep } from '@/utils/utils'
import { ClusterRequest, Group, GroupType } from '@/core/GroupManager'
import { useMapRenderer } from '@/mixins/mapview/useMapRenderer'

// Components
import MapMenu from './MapMenu.vue'
import Toolbar from './Toolbar.vue'
import Resizable from '../Resizable.vue'

const BORDER_WIDTH = 0.05
const WHITE_TINT = '#FFFFFF'
const DIMMED_TINT = '#CCCCCC'
const SELECTED_TINT = '#5DACFF'

const data = useDataStore()
const media = useMediaStore()
const columnStore = useColumnStore()
const props = defineProps<{
    tab: TabManager
    // The collection pipeline this map renders (M4 — resolved per-view by the
    // parent ViewPanel). Map display options below belong to the specific view.
    collection: CollectionManager
    // Per-view map display options (Pillar F).
    mapOptions: MapOptions
}>()

const canvasContainer = ref<HTMLElement | null>(null)
const { map: renderer, hoverInstanceId } = useMapRenderer(canvasContainer)

// State
const mouseMode = ref('pan')
const mapWidth = ref(1000)
const lastValiderHoverId = ref(hoverInstanceId.value)
const hasAtlas = ref(true)

const groups = ref<MapGroup[]>([])
const defaultColor = '#777777'

let sha1ToPoint: { [sha1: string]: PointData } = {}
let groupToPoints: { [groupId: number]: string[] } = {}
const selectedGroups = ref<{ [groupId: number]: boolean }>({})
const points = shallowRef<PointData[]>([])

// Tracks the latest showMap call to cancel stale concurrent invocations
let showMapToken = 0
// Stores args needed to call createMap once the renderer is ready
let pendingCreateMap: { atlas: any; points: PointData[]; showAsPoint: boolean } | null = null

// The group the map's cluster button clusters: the collection root, i.e. everything the map
// shows. Clustering goes through the collection like everywhere else (ClusterManager.cluster),
// so the clusters are grafted into the REAL tree and every view sees them — the map just reads
// them back out of the tree in generateGroups().
const rootGroupId = computed(() => (props.collection.version.value, props.collection.result?.root?.id))

// The collection's current images, for the toolbar's 'map' action. Read from the root group's
// slots (the tree's own membership) — `root.images` no longer exists.
const rootInstances = computed<Instance[]>(() => {
    props.collection.version.value
    const slots = props.collection.result?.root?.slots ?? []
    const ids = columnStore.instanceIds()
    return slots.map(slot => ({ id: ids[slot] })) as Instance[]
})

function cluster(req: ClusterRequest) {
    const id = rootGroupId.value
    if (id == null) return
    props.collection.cluster(id, req)
}

const isClustering = computed(() => {
    props.collection.version.value
    const id = rootGroupId.value
    return id != null && props.collection.isClustering(id)
})


function computeBox(sha1s: string[], color: string) {
    let minX = 0, minY = 0, maxX = 0, maxY = 0
    let initialized = false
    for (let i = 0; i < sha1s.length; i++) {
        let p = sha1ToPoint[sha1s[i]]
        if (!p) continue
        if (!initialized) {
            minX = p.x; minY = p.y; maxX = p.x; maxY = p.y
            initialized = true
        } else {
            minX = Math.min(minX, p.x); minY = Math.min(minY, p.y)
            maxX = Math.max(maxX, p.x); maxY = Math.max(maxY, p.y)
        }
    }
    return { minX, minY, maxX, maxY, color }
}

function computeName(group: Group, index: number = 0) {
    if (group.name) return group.name
    if (group.meta.propertyValues?.length) {
        const value = group.meta.propertyValues[0]
        const prop = data.properties[value.propertyId]
        if (isTag(prop.type)) {
            return data.tags[value.value]?.value ?? 'undefined'
        } else {
            return prop.name + ': ' + value.value
        }
    }
    return 'Group ' + index
}

function updateColors() {
    // Reset points
    points.value.forEach(p => {
        p.color = defaultColor
        p.borderColor = defaultColor
        p.border = 0.0
        p.tint = WHITE_TINT
        p.tintAlpha = 0.0
        p.z = 1.0
    })

    const hasHover = Object.keys(selectedGroups.value).length > 0
    for (let group of groups.value) {
        const isHover = selectedGroups.value[group.id]
        for (let point of group.points) {
            point.border = BORDER_WIDTH
            point.borderColor = group.color
            if (isHover) {
                point.tintAlpha = 0.0
                point.z = 1.1
            } else if (hasHover) {
                point.tintAlpha = 1.0
                point.tint = DIMMED_TINT
                point.z = 1.0
            } else {
                point.tintAlpha = 0.0
                point.z = 1.0
            }
        }
    }

    // Color selected images (global selection, note §5 step 2)
    columnStore.getSelectedIds().forEach(id => {
        const p = sha1ToPoint[data.instances[id].sha1]
        if (p) {
            p.tint = SELECTED_TINT
            p.tintAlpha = 0.8
        }
    })

    if (renderer.value) {
        renderer.value.updateBorder()
        renderer.value.updateTints()
        renderer.value.updatePosition()
    }
}

// Build the colored map groups from the collection's REAL group tree — the map has no group
// state of its own. 'property' colors by the top level of the property tree; 'cluster' colors by
// the cluster groups grafted under the root by ClusterManager.cluster().
// Membership is read from `slots` (the tree's own representation) and mapped to sha1s, since a
// map point is identified by sha1.
function generateGroups() {
    const root = props.collection.result?.root
    const children: Group[] = root?.children ?? []
    const groupList = props.mapOptions.groupOption === 'property'
        ? children.filter(g => g.type !== GroupType.Cluster)
        : children.filter(g => g.type === GroupType.Cluster)

    // Only the images actually on the map count: a group's sha1s, restricted to drawn points.
    const sha1s = columnStore.sha1s()
    const groupSha1s = new Map<number, string[]>()
    const kept: Group[] = []
    for (const g of groupList) {
        const list: string[] = []
        const seen = new Set<string>()
        for (const slot of g.slots ?? []) {
            const sha1 = sha1s[slot]
            if (!sha1 || seen.has(sha1) || !(sha1 in sha1ToPoint)) continue
            seen.add(sha1)
            list.push(sha1)
        }
        if (!list.length) continue
        groupSha1s.set(g.id, list)
        kept.push(g)
    }

    if (!kept.length) {
        groups.value = []
        groupToPoints = {}
        updateColors()
        return
    }

    const colors = generateColors(kept.length)

    const res: MapGroup[] = []
    groupToPoints = {}

    kept.forEach((g, index) => {
        let groupColor = colors[index]

        // Check for tag colors
        const propId = g.meta?.propertyValues?.[0]?.propertyId
        if (propId) {
            const property = data.properties[propId]
            if (isTag(property.type)) {
                const value = g.meta.propertyValues[0].value
                if (value !== undefined) {
                    groupColor = Colors[data.tags[value].color].color
                } else {
                    groupColor = greyColor.color
                }
            }
        }

        const groupSha1List = groupSha1s.get(g.id) ?? []
        groupToPoints[g.id] = groupSha1List
        const grpPoints = Array.from(new Set(groupSha1List.map(sha1 => sha1ToPoint[sha1]).filter(Boolean)))

        res.push({
            id: g.id,
            name: computeName(g, index),
            count: groupSha1List.length,
            color: groupColor,
            box: computeBox(groupSha1List, groupColor),
            points: grpPoints
        })
    })

    groups.value = res
    updateColors()
}

async function showMap(mapId: number) {
    if (!media.maps[mapId]) return

    // Bug 5: cancel any stale concurrent call
    const token = ++showMapToken

    if (!media.maps[mapId].data) await media.loadMapData(mapId)
    if (token !== showMapToken) return

    const newSha1ToPoint: { [sha1: string]: PointData } = {}
    const res: PointData[] = []
    const values = media.maps[mapId].data

    // The map only draws what the collection currently keeps. Read from the filter result's
    // slots (its own representation); fall back to all sha1s when it isn't ready yet.
    const filterSlots = props.collection.filterManager.result?.slots
    const allSha1s = columnStore.sha1s()
    const validSha1s = new Set<string>()
    if (filterSlots?.length) {
        for (let i = 0; i < filterSlots.length; i++) {
            const sha1 = allSha1s[filterSlots[i]]
            if (sha1) validSha1s.add(sha1)
        }
    } else {
        for (let i = 0; i < values.length; i += 3) validSha1s.add(values[i])
    }

    // Build sha1 → {id, ratio} from columnStore in one pass (replaces removed data.sha1Index)
    const sha1Array = columnStore.sha1s()
    const idArray = columnStore.instanceIds()
    const sha1ToId: { [sha1: string]: number } = {}
    for (let s = 0; s < columnStore.slotCount(); s++) {
        const sh = sha1Array[s]
        if (sh && !(sh in sha1ToId)) sha1ToId[sh] = idArray[s]
    }

    for (let i = 0; i < values.length; i += 3) {
        const sha1 = values[i]
        if (!validSha1s.has(sha1)) continue

        const instanceId = sha1ToId[sha1]
        if (instanceId === undefined) continue

        const x = values[i + 1]
        const y = values[i + 2]
        const entry = data.instances[instanceId]
        const ratio = (entry?.width && entry?.height) ? entry.width / entry.height : 1

        const p: PointData = {
            id: instanceId,
            x: x,
            y: y,
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
    generateGroups()

    const atlas = media.atlas
    if (!atlas) {
        hasAtlas.value = false
        return
    }

    // Bug 4: if renderer isn't ready yet, store args so the renderer watcher can call createMap
    if (renderer.value) {
        renderer.value.createMap(atlas, points.value, props.mapOptions.showPoints)
    } else {
        pendingCreateMap = { atlas, points: points.value, showAsPoint: props.mapOptions.showPoints }
    }
}

// Event Handlers
function onGroupHover(ev: { groupId: number, value: boolean }) {
    if (ev.value) {
        selectedGroups.value[ev.groupId] = true
    } else {
        delete selectedGroups.value[ev.groupId]
    }
    selectedGroups.value = { ...selectedGroups.value }
    updateColors()
}

const handleLasso = (selectedPoints: PointData[]) => {
    let ids: number[] = []
    for (let point of selectedPoints) {
        const instanceIds = columnStore.getInstancesBySha1(point.sha1)
        if (instanceIds.length) ids.push(...instanceIds)
    }
    if (mouseMode.value == 'lasso-plus') props.collection.selectImages(ids)
    if (mouseMode.value == 'lasso-minus') props.collection.unselectImages(ids)
}

async function deleteMap(mapId: number) {
    await media.deleteMap(mapId)
}

function onGroupManager() {
    showMap(props.mapOptions.selectedMap)
}

// Drop the map's clusters — the same op as the tree view's "close clusters", on the real tree.
function removeClusters() {
    const id = rootGroupId.value
    if (props.mapOptions.groupOption == 'cluster' && id != null) {
        props.collection.delCustomGroups(id, true)
    }
}

// Watchers
watch(mouseMode, (newMode) => { renderer.value?.setMouseMode(newMode) })
watch(() => columnStore.selectionVersion.value, () => updateColors())
watch(() => props.mapOptions.selectedMap, (mapId) => { if (mapId != null) showMap(mapId) })
watch(() => props.mapOptions.groupOption, () => generateGroups())
watch(() => props.mapOptions.showPoints, (val) => renderer.value?.setShowAsPoint(val))
watch(() => props.mapOptions.imageSize, (val) => renderer.value?.setImageSize(val))
watch(hoverInstanceId, () => {
    if(hoverInstanceId.value) {
        lastValiderHoverId.value = hoverInstanceId.value
    }
})

watch(renderer, (r) => {
    if (r) {
        r.onPointSelection = handleLasso
        r.setImageSize(props.mapOptions.imageSize)
        // Bug 4: flush a createMap call that arrived before the renderer was ready
        if (pendingCreateMap) {
            r.createMap(pendingCreateMap.atlas, pendingCreateMap.points, pendingCreateMap.showAsPoint)
            pendingCreateMap = null
        } else if (points.value.length > 0 && r.atlasLayers) {
            updateColors()
        }
    }
})

watch(mapWidth, () => console.log("map width", mapWidth.value))

watch(() => media.atlas, async () => {
    showMap(props.mapOptions.selectedMap)
})

// React to result changes via the version tick (note §3, step 1).
watch(() => props.collection.version.value, onGroupManager)

onMounted(async () => {
    await media.loadMaps()
    showMap(props.mapOptions.selectedMap)
    if (renderer.value) renderer.value.setMouseMode(mouseMode.value)
})
</script>

<template>
    <div class="main-layout">
        <div class="toolbar-container">
            <Toolbar
                v-model:mouse-mode="mouseMode"
                v-model:image-size="props.mapOptions.imageSize"
                v-model:show-point="props.mapOptions.showPoints"
                :selected-map="props.mapOptions.selectedMap"
                @update:selected-map="id => props.mapOptions.selectedMap = id"
                :color-option="props.mapOptions.groupOption"
                @update:color-option="opt => { props.mapOptions.groupOption = opt }"
                :has-maps="media.hasMaps"
                :images="rootInstances"
                :clustering="isClustering"
                @cluster="cluster"
                @delete:map="deleteMap"
            />
        </div>

        <div class="map-view-container">
            <Resizable @resize="s => mapWidth = s" class="map-resizable-wrapper" :disabled="true">
                <div class="map-container" 
                     :class="{ 'cursor-grab': mouseMode == 'pan', 'cursor-lasso': mouseMode.startsWith('lasso') }">
                    <div ref="canvasContainer" class="canvas-wrapper"></div>
                </div>
            </Resizable>

            <MapMenu 
                v-model:selected-map="props.mapOptions.selectedMap"
                v-model:color-option="props.mapOptions.groupOption" 
                :hover-image-id="lastValiderHoverId"
                :groups="groups" 
                @hover-group="onGroupHover"
                @click-group="g => renderer?.lookAtRect(g.box)"
                @removeClusters="removeClusters"
            />
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

.map-resizable-wrapper {
    flex-grow: 1;
    flex-shrink: 1;
    min-width: 0; /* Important: Allows map to shrink when menu expands */
    height: 100%;
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
    background-color: white;
}

.preview-overlay {
    position: absolute;
    top: 10px;
    right: 300px; /* Positioned to the left of an expanded menu */
    z-index: 10;
    max-height: 80%;
    pointer-events: none;
}

.cursor-grab { cursor: grab; }
.cursor-lasso { cursor: crosshair; }
</style>