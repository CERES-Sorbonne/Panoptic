<script setup lang="ts">
import { useDataStore } from '@/data/dataStore';
import { defineProps, defineEmits, computed } from 'vue'
import CenteredImage from '../images/CenteredImage.vue';

const data = useDataStore()

const props = defineProps<{
    sha1s: string[]
}>()
const emits = defineEmits(['update:mouseMode'])

function changeTool(tool: string) {
    emits('update:mouseMode', tool)
}


const images = computed(() => {
    let slice = props.sha1s.slice(0, 100)
    return slice.map(sha1 => data.sha1Index[sha1][0])
})

function test() {
    let nb = () => Math.random()*10000
    let arr = Array(1_000_000)
    
    let map = new Map()
    
    for(let i = 0; i < arr.length; i++) {
        arr[i] = nb()
    }
    // let subset = new Set(arr.slice(1, 500_000))
    arr.forEach((a,i) => map.set(i, a))
    let now = performance.now()
    let arr2 = Array.from(map.values())
    console.log(map[3])
    // console.log(arr2.slice(0, 100))
//     // arr.sort((a, b) => a - b)
//     let set = new Set(arr)
//     // arr.slice(1, 500_000).forEach(n => set.delete(n))
 
//     set = set.difference(subset)
//     // let arr2 = Array.from(new Set(arr))
//    let arr2 = Array.from(set)



    console.log(performance.now() - now)
}

</script>

<template>
    <div class="glass-box" style="overflow: auto; height: 100%;" @click="test">
        <CenteredImage :image="i" v-for="i in images" :width="100" :height="100" />
    </div>
</template>

<style scoped>
.glass-box {
    padding: 4px;
    background: rgba(195, 207, 217, 0.219);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    border-right: 1px solid rgba(195, 207, 217, 0.117);
    box-shadow: 0 0 2px 2px rgb(195, 207, 217);
    border-radius: 5px;
    column-gap: 4px;
    display: flex;
    flex-direction: column;
    row-gap: 8px;
}

.tool {
    color: rgb(0, 0, 0);
    line-height: 100%;
    padding: 4px;
    border-radius: 5px;
    cursor: pointer;
    
    transition: background-color 0.3s ease, color 0.3s ease;
}

.tool:hover {
    background-color: #89b0cd;
}

.selected, .selected:hover {
    color: rgb(255, 255, 255);
    background-color: #384955;
}
</style>