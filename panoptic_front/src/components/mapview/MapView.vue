<script setup lang="ts">
import { defineProps, ref, shallowRef, onMounted, watch, onUnmounted, nextTick, computed } from 'vue'
import { ActionResult, Colors, Instance, MapGroup } from '@/data/models'
import { useDataStore } from '@/data/dataStore'
import { TabManager } from '@/core/TabManager'
import { generateColors, isTag } from '@/utils/utils'
import { BoundingBox, PointData } from '@/mixins/mapview/useMapLogic'
import MapMenu from './MapMenu.vue'
import ImageMap from './ImageMap.vue'
import { Group } from '@/core/GroupManager'
import * as THREE from 'three'
import { objValues } from '@/data/builder'
import Toolbar from './Toolbar.vue'
import ImagePreview from './ImagePreview.vue'

const data = useDataStore()

const props = defineProps<{
    tab: TabManager
}>()

// --- Image Map Configuration Parameters ---
const baseImageSize = ref(10)
const maxImageSize = ref(250)
const minImageSize = ref(20)

const mouseMode = ref('pan')

const spatialFunction = ref({
    function: '',
    context: undefined
})
const groups = ref<MapGroup[]>([])
const defaultColor = '#4A90E2'
let clusters = []

let sha1ToPoint: { [sha1: string]: PointData } = {}

const selectedGroups = ref<{ [groupId: number]: boolean }>({})
let groupToPoints: { [groupId: number]: string[] } = {}

const selectedPoints = computed(() => {
    let ids = Object.keys(props.tab.collection.groupManager.selectedImages.value).map(Number)
    let instances = ids.map(i => data.instances[i])
    const res: { [sha1: string]: boolean } = {}
    for (let inst of instances) {
        res[inst.sha1] = true
    }
    console.log(res)
    return res
})

const selectedPointsList = computed(() => Object.keys(selectedPoints.value))
// ------------------------------------------

let points = shallowRef<PointData[]>([])
const mapElem = ref(null)

function colorGroups(groupList, groupColorMap) {
    if (!groupList.length) return

    const sha1ToGroupId = {}

    // ... (Mapping sha1 to groupId remains the same)
    for (let group of groupList) {
        for (let img of group.images) {
            sha1ToGroupId[img.sha1] = group.id
        }
    }

    const pointList = points.value
    for (let point of pointList) {
        let groupId = sha1ToGroupId[point.sha1]
        // Direct color lookup using the Group ID
        let pointColor = groupColorMap[groupId]

        point.color = pointColor // Assign color
        point.border = true
    }

    points.value = [...pointList]
    mapElem.value.updatePoints()
}

function clearColors() {
    const ps = points.value
    ps.forEach(p => {
        p.color = defaultColor
        p.border = false
    })
    mapElem.value.updatePoints()
}

async function showMap(mapId: number) {
    if (!data.maps[mapId]) {
        return
    }
    if (!data.maps[mapId].data) {
        await data.loadMapData(mapId)
    }

    sha1ToPoint = {}
    console.log('show map')
    const res = []
    const values = data.maps[mapId].data
    for (let i = 0; i < values.length; i += 3) {
        const sha1 = values[i]
        const x = values[i + 1]
        const y = values[i + 2]

        const img = data.sha1Index[sha1][0]
        const p: PointData = {
            x: x,
            y: y,
            color: defaultColor,
            sha1: sha1,
            ratio: img.containerRatio
        }
        res.push(p)
        sha1ToPoint[sha1] = p
    }
    points.value = res
    generateGroups()
}

function generateGroups() {
    let groupList: Group[] = []
    if (props.tab.state.mapOptions.groupOption == 'property') {
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

    const groupToColor = {}
    groupList.forEach((g, index) => groupToColor[g.id] = colors[index])

    const propId = groupList[0]?.meta?.propertyValues[0].propertyId
    if (propId) {
        const property = data.properties[propId]
        if (isTag(property.type)) {
            for (let group of groupList) {
                const value = group.meta.propertyValues[0].value
                if (value != undefined) {
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
        res.push({
            id: g.id,
            name: computeName(g),
            count: g.images.length,
            color: groupToColor[g.id],
            box: computeBox(g.images, groupToColor[g.id])
        })
    })
    colorGroups(groupList, groupToColor)
    groups.value = res
}

function computeBox(images: Instance[], color) {
    let minX, minY, maxX, maxY = 0
    for (let i = 0; i < images.length; i++) {
        let img = images[i]
        let p = sha1ToPoint[img.sha1]
        if (!p) continue
        if (i == 0) {
            minX = p.x
            minY = p.y
            maxX = p.x
            maxY = p.y
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
        }
        else {
            return prop.name + ': ' + value.value
        }
    }

    return 'Group ' + index
}

function showClusters(cc) {
    clusters = cc
    generateGroups()
}

// function getSelectedPoints() {
//     const selectedGroupKeys = Object.keys(selectedGroups.value).map(Number)
//     selectedPoints.value = {} // Clear selected points if no group is selected
//     // Check if any group is currently selected
//     if (selectedGroupKeys.length === 0) {
//         return
//     }
//     // Get the first selected group ID
//     let group = selectedGroupKeys[0]

//     // Check if the group ID has an entry in groupToPoints before iterating
//     if (groupToPoints[group]) {
//         groupToPoints[group].forEach(sha1 => {
//             selectedPoints.value[sha1] = true
//         })
//     }

// }

function onGroupHover(ev: { groupId: number, value: boolean }) {
    if (ev.value) {
        selectedGroups.value[ev.groupId] = true
        // let ids = []
        // for(let sha1 of groupToPoints[ev.groupId]) {
        //     ids.push(...data.sha1Index[sha1].map(i => i.id))
        // }
        // props.tab.collection.groupManager.selectImages(ids)
        // groups.value = [...groups.value]
        // getSelectedPoints()
        nextTick(() => mapElem.value.render())
    } else {
        delete selectedGroups.value[ev.groupId]
        let ids = []
        // for(let sha1 of groupToPoints[ev.groupId]) {
        //     ids.push(...data.sha1Index[sha1].map(i => i.id))
        // }
        // props.tab.collection.groupManager.unselectImages(ids)
        // groups.value = [...groups.value]
        // getSelectedPoints()
        nextTick(() => mapElem.value.render())
        mapElem.value.render()
    }
}

const handleLasso = (points: PointData[]) => {
    let ids = []
    for (let point of points) {
        ids.push(...data.sha1Index[point.sha1].map(i => i.id))
    }
    if (mouseMode.value == 'lasso-plus') {
        props.tab.collection.groupManager.selectImages(ids)
    }
    if (mouseMode.value == 'lasso-minus') {
        props.tab.collection.groupManager.unselectImages(ids)
    }
}

watch(selectedPoints, () => nextTick(() => mapElem.value.render()))

watch(() => props.tab.state.mapOptions.selectedMap, (mapId) => {
    if (mapId == null) {
        return
    }
    showMap(mapId)
})

watch(() => props.tab.state.mapOptions.groupOption, (val) => {
    // if(val == 'property') {
    //     clusters = []
    // }
    generateGroups()
})

watch(() => props.tab.state.mapOptions.showBoxes, (val) => mapElem.value.updateShowBoxes(val))

watch(() => props.tab.state.mapOptions, () => props.tab.saveState(), { deep: true })

onMounted(async () => {
    props.tab.collection.groupManager.onResultChange.addListener(generateGroups)
    await data.loadMaps()
    showMap(props.tab.state.mapOptions.selectedMap)
})

onUnmounted(() => {
    props.tab.collection.groupManager.onResultChange.removeListener(generateGroups)
})

</script>

<template>
    <div class="map-view-container">
        <div class="map-container"
            :class="{ 'cursor-grab': mouseMode == 'pan', 'cursor-lasso': mouseMode.startsWith('lasso') }">
            <ImageMap :points="points" :point-size="10" :show-images="props.tab.state.mapOptions.showImages"
                :show-points="props.tab.state.mapOptions.showPoints" :show-boxes="props.tab.state.mapOptions.showBoxes"
                background-color="#FFFFFF" :base-image-size="baseImageSize" :mouse-mode="mouseMode"
                :selected-points="selectedPoints" :max-image-size="maxImageSize" :min-image-size="minImageSize"
                :groups="groups" :selectedGroups="selectedGroups" ref="mapElem" @lasso="handleLasso" />
        </div>
        <div class="toolbar">
            <Toolbar v-model:mouse-mode="mouseMode" />
        </div>
        <div class="menu">
            <MapMenu v-model:selected-map="props.tab.state.mapOptions.selectedMap"
                v-model:show-images="props.tab.state.mapOptions.showImages"
                v-model:color-option="props.tab.state.mapOptions.groupOption"
                v-model:show-boxes="props.tab.state.mapOptions.showBoxes"
                v-model:show-points="props.tab.state.mapOptions.showPoints" v-model:base-image-size="baseImageSize"
                :groups="groups" v-model:max-image-size="maxImageSize" v-model:min-image-size="minImageSize"
                v-model:spatial-function="spatialFunction" @clusters="showClusters" @hover-group="onGroupHover"
                :images="tab.collection.groupManager.result.root.images" />
        </div>
        <div v-if="selectedPointsList.length" class="preview">
            <ImagePreview :sha1s="selectedPointsList"/>
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
}

.map-container {
    flex-grow: 1;
    /* margin-top: 8px; */
    z-index: 1;
}

.cursor-grab {
    cursor: grab;
}

.cursor-lasso {
    cursor: crosshair;
}

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
    /* background-color: red; */
    transform: translate(-50%, 0);
    /* background-color: blue; */
}
</style>