<script setup lang="ts">
import { defineProps, ref, shallowRef, onMounted, watch } from 'vue'
import { ActionResult } from '@/data/models'
import { useDataStore } from '@/data/dataStore'
import { TabManager } from '@/core/TabManager'
import { generateColors } from '@/utils/utils'
import { PointData } from '@/mixins/useMapLogic'
import MapMenu from './MapMenu.vue'
import ImageMap from './ImageMap.vue'

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
const colorOption = ref('property')
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

function colorGroups() {
    let groupManager = props.tab.collection.groupManager
    let groups = groupManager.result.root.children

    if (groups.length == 0) return

    let colors = generateColors(groups.length)
    const groupToColor = {}
    const idToGroupId = {}
    groups.forEach((g, index) => groupToColor[g.id] = index)
    for (let group of groups) {
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
            color: '#FF00FF',
            sha1: sha1,
            ratio: img.containerRatio
        }
        res.push(p)
    }
    points.value = res
}

watch(selectedMap, (mapId) => {
    if (mapId == null) {
        return
    }
    showMap(mapId)
})

onMounted(() => {
    data.loadMaps()
    showMap(selectedMap.value)
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
            <MapMenu v-model:selected-map="selectedMap" v-model:show-images="showImages" v-model:color-option="colorOption"
                v-model:show-points="showPoints" v-model:base-image-size="baseImageSize"
                v-model:max-image-size="maxImageSize" v-model:min-image-size="minImageSize"
                v-model:spatial-function="spatialFunction" @result="showResult" @color-groups="colorGroups" />
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
}
</style>