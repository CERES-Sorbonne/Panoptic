<script setup lang="ts">
import { defineProps, defineEmits, ref, shallowRef } from 'vue'
import ActionSelect from './actions/ActionSelect.vue';
import FunctionButton from './actions/FunctionButton.vue';
import ActionSelectButton from './actions/ActionSelectButton.vue';
import { ActionResult } from '@/data/models';
import ImageMap, { PointData } from './mapview/ImageMap.vue';
import { useDataStore } from '@/data/dataStore';

const data = useDataStore()

const emits = defineEmits([])

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
    
    mapElem.value.updatePoints(points)
}

</script>

<template>
    <div class="d-flex flex-column">
        <div class="d-flex pt-1" style="column-gap: 4px; align-items: center;">
            <div>Select Maping Function</div>
            <ActionSelectButton :size="15" :action="'map'" @changed="e => spatialFunction = e" @result="showResult" />
            <div><input type="checkbox" v-model="showImages" /> show Images</div>
        </div>
        <div class="flex-grow-1" style="margin-right: 10px; margin-top: 8px;">
            <ImageMap :points="points" :point-size="0.05" :show-images="showImages" :show-points="showPoints" background-color="#FFFFFF" ref="mapElem"/>
        </div>
    </div>
</template>

<style scoped></style>