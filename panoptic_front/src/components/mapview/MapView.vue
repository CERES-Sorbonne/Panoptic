<script setup lang="ts">
import { ref, shallowRef, onMounted, watch, computed } from 'vue'
import { Colors, Instance, MapGroup, PointData } from '@/data/models'
import { useDataStore } from '@/data/dataStore'
import { TabManager } from '@/core/TabManager'
import { generateColors, isTag } from '@/utils/utils'
import { Group } from '@/core/GroupManager'
import { useMapRenderer } from '@/mixins/mapview/useMapRenderer'
import { apiGetAtlas } from '@/data/apiProjectRoutes' // Import needed for atlas loading

// Components
import MapMenu from './MapMenu.vue'
import Toolbar from './Toolbar.vue'
import ImagePreview from './ImagePreview.vue'

const BORDER_WIDTH = 0.05
const WHITE_TINT = '#FFFFFF'
const DIMMED_TINT = '#888888'
const SELECTED_TINT = '#5DACFF'

const data = useDataStore()

const props = defineProps<{
    tab: TabManager
}>()

// --- Refs & State ---
const canvasContainer = ref<HTMLElement | null>(null)
// Initialize the renderer controller directly with the container ref
const { map: renderer } = useMapRenderer(canvasContainer)

// Image Map Configuration
const baseImageSize = ref(3)
const maxImageSize = ref(5)
const minImageSize = ref(10)
const showPoints = ref(false)
const mouseMode = ref('pan')

const spatialFunction = ref({
    function: '',
    context: undefined
})

const groups = ref<MapGroup[]>([])
const defaultColor = '#4A90E2'
let clusters: Group[] = []

// Fast lookups
let sha1ToPoint: { [sha1: string]: PointData } = {}
let groupToPoints: { [groupId: number]: string[] } = {}
const selectedGroups = ref<{ [groupId: number]: boolean }>({})

const points = shallowRef<PointData[]>([])

// --- Computeds ---

const selectedPoints = computed(() => {
    let ids = Object.keys(props.tab.collection.groupManager.selectedImages.value).map(Number)
    let instances = ids.map(i => data.instances[i])
    const res: { [sha1: string]: boolean } = {}
    
    // Add explicitly selected images
    for (let inst of instances) {
        res[inst.sha1] = true
    }

    // Add images from selected groups
    for (let groupId of Object.keys(selectedGroups.value).map(Number)) {
        if (groupToPoints[groupId]) {
            for (let sha1 of groupToPoints[groupId]) {
                res[sha1] = true
            }
        }
    }
    return res
})

const selectedPointsList = computed(() => Object.keys(selectedPoints.value))

// --- Logic ---

function colorGroups() {
    const hasHover = Object.keys(selectedGroups.value).length > 0
    
    for (let group of groups.value) {
        const isHover = selectedGroups.value[group.id]
        for (let point of group.points) {
            point.border = BORDER_WIDTH
            point.borderColor = group.color
            if (isHover) {
                point.tintAlpha = 0.0
                point.z = 1.1 // Bring to front
            } else if (hasHover) {
                point.tintAlpha = 0.7
                point.tint = DIMMED_TINT
                point.z = 1.0
            } else {
                point.tintAlpha = 0.0
                point.z = 1.0
            }
        }
    }
}

function colorSelected() {
    const pointList = points.value
    const selected = props.tab.collection.groupManager.selectedImages.value
    const selectedSha1s = new Set<string>()

    Object.keys(selected).map(Number).forEach(id => selectedSha1s.add(data.instances[id].sha1))

    for (let point of pointList) {
        if (selectedSha1s.has(point.sha1)) {
            point.tint = SELECTED_TINT
            point.tintAlpha = 0.5
        }
    }
    // We don't need to reassign points.value since we mutated objects and will call update methods
}

function updateColors() {
    clearColors()
    colorGroups()
    colorSelected()
    
    // Direct communication with Renderer
    if (renderer.value) {
        renderer.value.updateBorder()
        renderer.value.updateTints()
        renderer.value.updatePosition() // Required if Z-index changed
    }
}

function clearColors() {
    points.value.forEach(p => {
        p.color = defaultColor
        p.border = 0.0
        p.tint = WHITE_TINT
        p.tintAlpha = 0.0
        p.z = 1.0
    })
}

async function showMap(mapId: number) {
    if (!data.maps[mapId]) return
    if (!data.maps[mapId].data) await data.loadMapData(mapId)

    sha1ToPoint = {}
    console.log('Loading map data...')
    
    const res: PointData[] = []
    const values = data.maps[mapId].data
    
    for (let i = 0; i < values.length; i += 3) {
        const sha1 = values[i]
        const x = values[i + 1]
        const y = values[i + 2]

        const img = data.sha1Index[sha1]?.[0]
        if (!img) continue // Safety check

        const p: PointData = {
            id: img.id, // Ensure ID is passed for selection logic
            x: x,
            y: y,
            z: 1.0,
            color: defaultColor,
            sha1: sha1,
            ratio: img.containerRatio,
            order: 1,
            border: 0.0,
            tintAlpha: 0.0,
            borderColor: '#000000'
        }
        res.push(p)
        sha1ToPoint[sha1] = p
    }
    
    points.value = res
    generateGroups()
    showPoints.value = true

    // Initialize Renderer with new data
    if (renderer.value) {
        const atlas = await apiGetAtlas(0) // Ideally this ID comes from map config
        renderer.value.createMap(atlas, points.value)
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

    if (!groupList.length && groups.value.length) {
        groups.value = []
        clearColors()
        return
    }

    const nb = groupList.length
    const colors = generateColors(nb)
    const groupToColor: Record<number, string> = {}
    
    groupList.forEach((g, index) => groupToColor[g.id] = colors[index])

    // Handle Tag Property Colors
    const propId = groupList[0]?.meta?.propertyValues?.[0]?.propertyId
    if (propId) {
        const property = data.properties[propId]
        if (isTag(property.type)) {
            for (let group of groupList) {
                const value = group.meta.propertyValues[0].value
                if (value !== undefined) {
                    groupToColor[group.id] = Colors[data.tags[value].color].color
                } else {
                    groupToColor[group.id] = '#777'
                }
            }
        }
    }

    const res: MapGroup[] = []
    groupToPoints = {}
    
    groupList.forEach((g) => {
        groupToPoints[g.id] = g.images.map(i => i.sha1)
        const grpPoints = Array.from(new Set(g.images.map(i => sha1ToPoint[i.sha1]).filter(Boolean)))
        
        res.push({
            id: g.id,
            name: computeName(g),
            count: g.images.length,
            color: groupToColor[g.id],
            box: computeBox(g.images, groupToColor[g.id]),
            points: grpPoints
        })
    })
    
    groups.value = res
    updateColors()
}

function computeBox(images: Instance[], color: string) {
    let minX, minY, maxX, maxY = 0
    let initialized = false

    for (let i = 0; i < images.length; i++) {
        let img = images[i]
        let p = sha1ToPoint[img.sha1]
        if (!p) continue
        
        if (!initialized) {
            minX = p.x; minY = p.y; maxX = p.x; maxY = p.y
            initialized = true
        } else {
            minX = Math.min(minX, p.x)
            minY = Math.min(minY, p.y)
            maxX = Math.max(maxX, p.x)
            maxY = Math.max(maxY, p.y)
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

function showClusters(cc: any[]) {
    clusters = cc
    generateGroups()
}

function onGroupHover(ev: { groupId: number, value: boolean }) {
    if (ev.value) {
        selectedGroups.value[ev.groupId] = true
    } else {
        delete selectedGroups.value[ev.groupId]
    }
    // Trigger reactivity for watcher if necessary, though simpler is usually better
    selectedGroups.value = { ...selectedGroups.value }
    updateColors()
}

const handleLasso = (selectedPoints: PointData[]) => {
    let ids: number[] = []
    for (let point of selectedPoints) {
        if(data.sha1Index[point.sha1]) {
            ids.push(...data.sha1Index[point.sha1].map(i => i.id))
        }
    }
    
    if (mouseMode.value == 'lasso-plus') {
        props.tab.collection.groupManager.selectImages(ids)
    }
    if (mouseMode.value == 'lasso-minus') {
        props.tab.collection.groupManager.unselectImages(ids)
    }
}

// --- Watchers ---

// Update renderer mouse mode when UI changes
watch(mouseMode, (newMode) => {
    renderer.value?.setMouseMode(newMode)
})

// Sync Selection Colors
watch(props.tab.collection.groupManager.selectedImages, () => updateColors())

// Load map when selection changes
watch(() => props.tab.state.mapOptions.selectedMap, (mapId) => {
    if (mapId != null) showMap(mapId)
})

// Re-group when options change
watch(() => props.tab.state.mapOptions.groupOption, () => generateGroups())

// Bind Selection Event from Renderer
watch(renderer, (r) => {
    if (r) {
        r.onPointSelection = handleLasso
        // If we have points loaded but renderer just initialized (race condition fix)
        if (points.value.length > 0 && r.atlasLayers) {
            // Re-trigger visual updates if needed
             updateColors()
        }
    }
})

// Save state
watch(() => props.tab.state.mapOptions, () => props.tab.saveState(), { deep: true })

// --- Lifecycle ---

onMounted(async () => {
    props.tab.collection.groupManager.onResultChange.addListener(generateGroups)
    await data.loadMaps()
    showMap(props.tab.state.mapOptions.selectedMap)
})

onMounted(() => {
    // Safety check: ensure mouse mode is synced on startup
    if(renderer.value) renderer.value.setMouseMode(mouseMode.value)
})

// Cleanup
import { onUnmounted } from 'vue'
onUnmounted(() => {
    props.tab.collection.groupManager.onResultChange.removeListener(generateGroups)
})
</script>

<template>
    <div class="map-view-container">
        <div class="map-container"
            :class="{ 'cursor-grab': mouseMode == 'pan', 'cursor-lasso': mouseMode.startsWith('lasso') }">
            
            <div ref="canvasContainer" class="canvas-wrapper"></div>
            
        </div>

        <div class="toolbar">
            <Toolbar v-model:mouse-mode="mouseMode" />
        </div>

        <div class="menu">
            <MapMenu v-model:selected-map="props.tab.state.mapOptions.selectedMap"
                v-model:show-images="props.tab.state.mapOptions.showImages"
                v-model:color-option="props.tab.state.mapOptions.groupOption"
                v-model:show-boxes="props.tab.state.mapOptions.showBoxes"
                v-model:show-points="props.tab.state.mapOptions.showPoints" 
                v-model:base-image-size="baseImageSize"
                v-model:max-image-size="maxImageSize" 
                v-model:min-image-size="minImageSize"
                v-model:spatial-function="spatialFunction" 
                :groups="groups" 
                :images="tab.collection.groupManager.result.root.images" 
                @clusters="showClusters" 
                @hover-group="onGroupHover"
                />
        </div>

        <div v-if="selectedPointsList.length" class="preview">
            <ImagePreview :sha1s="selectedPointsList" />
        </div>
    </div>
</template>

<style scoped>
.map-view-container {
    padding: 0;
    margin: 0;
    position: relative;
    display: flex;
    height: 100%;
    width: 100%;
}

.map-container {
    flex-grow: 1;
    z-index: 1;
    overflow: hidden;
    position: relative;
}

.canvas-wrapper {
    width: 100%;
    height: 100%;
    background-color: white; /* Or your preferred background */
}

.cursor-grab { cursor: grab; }
.cursor-lasso { cursor: crosshair; }

.menu {
    position: absolute;
    top: 10px;
    left: 10px;
    z-index: 10;
}

.preview {
    position: absolute;
    top: 10px;
    right: 10px;
    z-index: 10;
    bottom: 10px;
    overflow: hidden;
    padding: 10px;
}

.toolbar {
    position: absolute;
    top: 10px;
    left: 50%;
    z-index: 10;
    transform: translate(-50%, 0);
}
</style>