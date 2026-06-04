<script setup lang="ts">
import { ref, shallowRef, onMounted, watch, computed, onUnmounted, nextTick } from 'vue'
import { Colors, greyColor, Instance, MapGroup, PointData } from '@/data/models'
import { useDataStore } from '@/data/dataStore'
import { useMediaStore } from '@/data/mediaStore'
import { useColumnStore } from '@/data/columnStore'
import { TabManager } from '@/core/TabManager'
import { generateColors, isTag, sleep } from '@/utils/utils'
import { Group } from '@/core/GroupManager'
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
let clusters: Group[] = []

let sha1ToPoint: { [sha1: string]: PointData } = {}
let groupToPoints: { [groupId: number]: string[] } = {}
const selectedGroups = ref<{ [groupId: number]: boolean }>({})
const points = shallowRef<PointData[]>([])

// Tracks the latest showMap call to cancel stale concurrent invocations
let showMapToken = 0
// Stores args needed to call createMap once the renderer is ready
let pendingCreateMap: { atlas: any; points: PointData[]; showAsPoint: boolean } | null = null

// Instances corresponding to map points — used for clustering so only visible images are clustered
const mapInstances = computed<Instance[]>(() =>
    points.value.map(p => data.instances[p.id]).filter(Boolean) as Instance[]
)


function computeBox(images: Instance[], color: string) {
    let minX = 0, minY = 0, maxX = 0, maxY = 0
    let initialized = false
    for (let i = 0; i < images.length; i++) {
        let img = images[i]
        let p = sha1ToPoint[img.sha1]
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

    // Color selected images
    const selected = props.tab.collection.groupManager.selectedImages.value
    Object.keys(selected).map(Number).forEach(id => {
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

function generateGroups() {
    let groupList: Group[] = []
    const groupOption = props.tab.state.mapOptions.groupOption

    if (groupOption === 'property') {
        groupList = props.tab.collection.groupManager.result.root.children
    } else {
        groupList = clusters
    }

    groupList = groupList.map(g => ({...g}))

    const validSha1s = new Set()
    points.value.forEach(p => validSha1s.add(p.sha1))

    for(let group of groupList) {
        group.images = group.images.filter(i => validSha1s.has(i.sha1))
    }

    groupList = groupList.filter(g => g.images.length > 0)
    groupList
    if (!groupList.length) {
        groups.value = []
        updateColors()
        return
    }

    const nb = groupList.length
    const colors = generateColors(nb)
    
    const res: MapGroup[] = []
    groupToPoints = {}
    
    groupList.forEach((g, index) => {
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

        groupToPoints[g.id] = g.images.map(i => i.sha1)
        const grpPoints = Array.from(new Set(g.images.map(i => sha1ToPoint[i.sha1]).filter(Boolean)))
        
        res.push({
            id: g.id,
            name: computeName(g, index),
            count: g.images.length,
            color: groupColor,
            box: computeBox(g.images, groupColor),
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

    // Bug 2: fall back to all sha1s when filter result isn't ready yet
    const filterImages = props.tab.collection.filterManager.result?.images
    const validSha1s = new Set<string>()
    if (filterImages) {
        filterImages.forEach(i => validSha1s.add(i.sha1))
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
        renderer.value.createMap(atlas, points.value, props.tab.state.mapOptions.showPoints)
    } else {
        pendingCreateMap = { atlas, points: points.value, showAsPoint: props.tab.state.mapOptions.showPoints }
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
    if (mouseMode.value == 'lasso-plus') props.tab.collection.groupManager.selectImages(ids)
    if (mouseMode.value == 'lasso-minus') props.tab.collection.groupManager.unselectImages(ids)
}

async function deleteMap(mapId: number) {
    await media.deleteMap(mapId)
}

function onGroupManager() {
    showMap(props.tab.state.mapOptions.selectedMap)
}

function removeClusters() {
    const groupOption = props.tab.state.mapOptions.groupOption

    if(groupOption == 'cluster') {
        clusters = []
        generateGroups()
    }
}

// Watchers
watch(mouseMode, (newMode) => { renderer.value?.setMouseMode(newMode) })
watch(props.tab.collection.groupManager.selectedImages, () => updateColors())
watch(() => props.tab.state.mapOptions.selectedMap, (mapId) => { if (mapId != null) showMap(mapId) })
watch(() => props.tab.state.mapOptions.groupOption, () => generateGroups())
watch(() => props.tab.state.mapOptions.showPoints, (val) => renderer.value?.setShowAsPoint(val))
watch(() => props.tab.state.mapOptions.imageSize, (val) => renderer.value?.setImageSize(val))
watch(hoverInstanceId, () => {
    if(hoverInstanceId.value) {
        lastValiderHoverId.value = hoverInstanceId.value
    }
})

watch(renderer, (r) => {
    if (r) {
        r.onPointSelection = handleLasso
        r.setImageSize(props.tab.state.mapOptions.imageSize)
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

watch(() => props.tab.state.mapOptions, () => props.tab.saveState(), {deep: true})

watch(() => media.atlas, async () => {
    showMap(props.tab.state.mapOptions.selectedMap)
})

onMounted(async () => {
    props.tab.collection.groupManager.onResultChange.addListener(onGroupManager)
    await media.loadMaps()
    showMap(props.tab.state.mapOptions.selectedMap)
    if (renderer.value) renderer.value.setMouseMode(mouseMode.value)
})

onUnmounted(() => {
    props.tab.collection.groupManager.onResultChange.removeListener(onGroupManager)
})
</script>

<template>
    <div class="main-layout">
        <div class="toolbar-container">
            <Toolbar
                v-model:mouse-mode="mouseMode"
                v-model:image-size="props.tab.state.mapOptions.imageSize"
                v-model:show-point="props.tab.state.mapOptions.showPoints"
                :selected-map="props.tab.state.mapOptions.selectedMap"
                @update:selected-map="id => props.tab.state.mapOptions.selectedMap = id"
                :color-option="props.tab.state.mapOptions.groupOption"
                @update:color-option="opt => {props.tab.state.mapOptions.groupOption = opt; props.tab.saveState();}"
                :has-maps="media.hasMaps"
                :images="tab.collection.groupManager.result.root?.images || []"
                :map-images="mapInstances"
                @clusters="cc => { clusters = cc; generateGroups()}"
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
                v-model:selected-map="props.tab.state.mapOptions.selectedMap"
                v-model:color-option="props.tab.state.mapOptions.groupOption" 
                :hover-image-id="lastValiderHoverId"
                :groups="groups" 
                :images="tab.collection.groupManager.result.root?.images || []"
                @clusters="cc => { clusters = cc; generateGroups() }" 
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