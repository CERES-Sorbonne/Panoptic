<script setup lang="ts">
import { defineProps, defineEmits, computed } from 'vue'

const props = defineProps<{ mouseMode: string }>()
const emits = defineEmits(['update:mouseMode'])

function changeTool(tool: string) {
    emits('update:mouseMode', tool)
}

</script>

<template>
    <div class="glass-box d-flex">
        <div class="tool" :class="{selected: props.mouseMode == 'pan'}" @click="changeTool('pan')"><i class="bi bi-hand-index-thumb"></i></div>
        <div class="tool" :class="{selected: props.mouseMode == 'lasso'}" @click="changeTool('lasso')"><i class="bi bi-plus-circle-dotted"></i></div>
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