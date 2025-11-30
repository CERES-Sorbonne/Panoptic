<script setup lang="ts">
import { defineProps, defineEmits, ref, shallowRef } from 'vue'
import ActionSelectButton from './actions/ActionSelectButton.vue'
import { ActionResult } from '@/data/models'
// Assuming ImageMap is the component you provided in the previous turn
import { useDataStore } from '@/data/dataStore'
import { TabManager } from '@/core/TabManager'
import { generateColors } from '@/utils/utils'
import { PointData } from '@/mixins/useMapLogic'
import ImageMap from './mapview/ImageMap.vue'

const data = useDataStore()

const props = defineProps<{
    tab: TabManager
}>()

const emits = defineEmits([])

// --- Image Map Configuration Parameters ---
// These match the props defined in the ImageMap component
const baseImageSize = ref(10) // Factor for base size calculation (World Units)
const maxImageSize = ref(250) // Maximum visual size (Pixels)
const minImageSize = ref(20) // Minimum visual size (Pixels)
// ------------------------------------------

let points = shallowRef<PointData[]>([
])

const showImages = ref(true)
const showPoints = ref(true)

const mapElem = ref(null)
const spatialFunction = ref({
    function: '',
    context: undefined
})

function showResult(res: ActionResult) {
    points.value = []
    const positions = res.value
    for (let sha1 in res.value) {
        const pos = positions[sha1]
        // Assuming data.sha1Index[sha1][0] contains necessary image metadata
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
    
    // mapElem.value.updatePoints(points) // Use the exposed function if needed, but watch on props handles it
}

function colorGroups() {
    let groupManager = props.tab.collection.groupManager
    let groups = groupManager.result.root.children

    if(groups.length == 0) return

    let colors = generateColors(groups.length)
    const groupToColor = {}
    const idToGroupId = {}
    groups.forEach((g, index) => groupToColor[g.id] = index)
    for(let group of groups) {
        for(let img of group.images) {
            idToGroupId[img.sha1] = group.id
        }
    }

    for(let point of points.value) {
        let groupId = idToGroupId[point.sha1]
        let colorIndex = groupToColor[groupId]
        point.color = colors[colorIndex]
        point.border = true
    }
    mapElem.value.updatePoints()
}

</script>

<template>
    <div class="d-flex flex-column">
        <div class="d-flex pt-1 flex-wrap" style="column-gap: 8px; row-gap: 4px; align-items: center;">
            <div class="fw-bold">Map Function:</div>
            <ActionSelectButton :size="15" :action="'map'" @changed="e => spatialFunction = e" @result="showResult" />
            
            <div><input type="checkbox" v-model="showImages" /> Show Images</div>
            <div><input type="checkbox" v-model="showPoints" /> Show Points</div>

            <div class="d-flex align-items-center" style="column-gap: 4px;">
                <label for="baseSizeSlider">Base Size (Factor):</label>
                <input 
                    id="baseSizeSlider" 
                    type="range" 
                    v-model.number="baseImageSize" 
                    min="1" 
                    max="50" 
                    step="0.5" 
                    style="width: 100px;"
                />
                <span>{{ baseImageSize.toFixed(1) }}</span>
            </div>

            <div class="d-flex align-items-center" style="column-gap: 4px;">
                <label for="minSizeSlider">Min Size (px):</label>
                <input 
                    id="minSizeSlider" 
                    type="range" 
                    v-model.number="minImageSize" 
                    min="5" 
                    max="100" 
                    step="1" 
                    style="width: 100px;"
                />
                <span>{{ minImageSize }}</span>
            </div>

            <div class="d-flex align-items-center" style="column-gap: 4px;">
                <label for="maxSizeSlider">Max Size (px):</label>
                <input 
                    id="maxSizeSlider" 
                    type="range" 
                    v-model.number="maxImageSize" 
                    min="50" 
                    max="500" 
                    step="10" 
                    style="width: 100px;"
                />
                <span>{{ maxImageSize }}</span>
            </div>

            <div class="bbb" @click="colorGroups()"> Color Groups</div>
        </div>
        
        <hr>

        <div class="flex-grow-1" style="margin-right: 10px; margin-top: 8px;">
            <ImageMap 
                :points="points" 
                :point-size="5" 
                :show-images="showImages" 
                :show-points="showPoints" 
                background-color="#FFFFFF" 
                :base-image-size="baseImageSize"
                :max-image-size="maxImageSize"
                :min-image-size="minImageSize"
                ref="mapElem"
            />
        </div>
    </div>
</template>

<style scoped>
/* Scoped styles can be added here */
.d-flex {
    display: flex;
}
.flex-column {
    flex-direction: column;
}
.flex-grow-1 {
    flex-grow: 1;
}
.align-items-center {
    align-items: center;
}
.pt-1 {
    padding-top: 0.25rem;
}
.flex-wrap {
    flex-wrap: wrap;
}
.fw-bold {
    font-weight: bold;
}
</style>