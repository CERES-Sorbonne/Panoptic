<script setup lang="ts">
import { defineProps, ref, shallowRef, onMounted, watch, onUnmounted } from 'vue'
import { ActionResult, MapGroup } from '@/data/models'
import { useDataStore } from '@/data/dataStore'
import { TabManager } from '@/core/TabManager'
import { generateColors } from '@/utils/utils'
import { PointData } from '@/mixins/useMapLogic'
import MapMenu from './MapMenu.vue'
import ImageMap from './ImageMap.vue'
import { Group } from '@/core/GroupManager'
import * as THREE from 'three'

const data = useDataStore()

const props = defineProps<{
    tab: TabManager
}>()

// --- Image Map Configuration Parameters ---
const baseImageSize = ref(10)
const maxImageSize = ref(250)
const minImageSize = ref(20)
const showImages = ref(true)
const showPoints = ref(true)
const selectedMap = ref<number>(null)
const spatialFunction = ref({
    function: '',
    context: undefined
})
const groupOption = ref('property')
const groups = ref<MapGroup[]>([])
const defaultColor = '#4A90E2'
let clusters = []
// ------------------------------------------

let points = shallowRef<PointData[]>([])
const mapElem = ref(null)

function showResult(res: ActionResult) {
    return
    points.value = []
    const positions = res.value
    for (let sha1 in res.value) {
        const pos = positions[sha1]
        const img = data.sha1Index[sha1][0]
        const p: PointData = {
            x: pos[0],
            y: pos[1],
            color: '#FF00FF',
            sha1: sha1,
            ratio: img.containerRatio
        }
        points.value.push(p)
    }
}

function colorGroups(groupList, colors) {
    const groupToColor = {}
    const idToGroupId = {}
    groupList.forEach((g, index) => groupToColor[g.id] = index)
    for (let group of groupList) {
        for (let img of group.images) {
            idToGroupId[img.sha1] = group.id
        }
    }

    for (let point of points.value) {
        let groupId = idToGroupId[point.sha1]
        let colorIndex = groupToColor[groupId]
        point.color = colors[colorIndex]
        point.border = true
    }
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
    }
    points.value = res
    generateGroups()
}

function generateGroups() {
    let groupList: Group[] = []
    if(groupOption.value == 'property') {
        groupList = props.tab.collection.groupManager.result.root.children
    } else {
        groupList = clusters
    }

    if(!groupList.length && groups.value.length) {
        groups.value = []
        clearColors()
        return
    }

    const nb = groupList.length
    const colors = generateColors(nb)

    groups.value = groupList.map((g, i) => ({
        id: g.id,
        name: g.name,
        count: g.images.length,
        color: colors[i]
    }))

    colorGroups(groupList, colors)
}

function showClusters(cc) {
    clusters = cc
    generateGroups()
}

watch(selectedMap, (mapId) => {
    if (mapId == null) {
        return
    }
    showMap(mapId)
})

watch(groupOption, (val) => {
    // if(val == 'property') {
    //     clusters = []
    // }
    generateGroups()
})

onMounted(() => {
    data.loadMaps()
    showMap(selectedMap.value)
    props.tab.collection.groupManager.onResultChange.addListener(generateGroups)
})

onUnmounted(() => {
    props.tab.collection.groupManager.onResultChange.removeListener(generateGroups)
})

</script>

<template>
    <div class="map-view-container">
        <div class="map-container">
            <ImageMap :points="points" :point-size="10" :show-images="showImages" :show-points="showPoints"
                background-color="#FFFFFF" :base-image-size="baseImageSize" :max-image-size="maxImageSize"
                :min-image-size="minImageSize" ref="mapElem" />
        </div>
        <div class="menu">
            <MapMenu v-model:selected-map="selectedMap" v-model:show-images="showImages" v-model:color-option="groupOption"
                v-model:show-points="showPoints" v-model:base-image-size="baseImageSize" :groups="groups"
                v-model:max-image-size="maxImageSize" v-model:min-image-size="minImageSize"
                v-model:spatial-function="spatialFunction" @result="showResult" @clusters="showClusters" :images="tab.collection.groupManager.result.root.images"/>
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
}

.menu {
    position: absolute;
    top: 10px;
    left: 10px;
    bottom: 0px;
}
</style>