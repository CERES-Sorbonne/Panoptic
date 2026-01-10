<script setup lang="ts">
import RangeInput from '../inputs/RangeInput.vue';


const props = defineProps<{
    mouseMode: string
    imageSize: number
    zoomDelay: number
    showPoint: boolean
}>()
const emits = defineEmits(['update:mouseMode', 'update:imageSize', 'update:zoomDelay', 'update:showPoint'])

function changeTool(tool: string) {
    emits('update:mouseMode', tool)
}

</script>

<template>
    <div class="glass-box d-flex">
        <div class="tool" :class="{ selected: props.showPoint }" @click="emits('update:showPoint', !props.showPoint)"><i
                class="bi bi-dot"></i></div>
        <div class="divider"></div>
        <div class="tool" :class="{ selected: props.mouseMode == 'pan' }" @click="changeTool('pan')"><i
                class="bi bi-hand-index-thumb"></i></div>
        <div class="tool" :class="{ selected: props.mouseMode == 'lasso-plus' }" @click="changeTool('lasso-plus')"><i
                class="bi bi-plus-circle-dotted"></i></div>
        <div class="tool" :class="{ selected: props.mouseMode == 'lasso-minus' }" @click="changeTool('lasso-minus')"><i
                class="bi bi-dash-circle-dotted"></i></div>
        <div class="divider"></div>
        <div class="tool-icon"><i class="bi bi-aspect-ratio"></i></div>
        <RangeInput style="width: 60px;" :min="1" :max="10" :modelValue="props.imageSize"
            @update:modelValue="e => emits('update:imageSize', e)" />
        <!-- <div class="divider"></div> -->
        <div class="tool-icon"><i class="bi bi-border"></i></div>
        <RangeInput style="width: 60px;" :min="1" :max="10" :modelValue="props.zoomDelay"
            @update:modelValue="e => emits('update:zoomDelay', e)" />

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

.tool-icon {
    color: rgb(0, 0, 0);
    line-height: 100%;
    padding: 4px 0px;
    border-radius: 5px;
    opacity: 0.7;
}

.tool:hover {
    background-color: #89b0cd;
}

.selected,
.selected:hover {
    color: rgb(255, 255, 255);
    background-color: #384955;
}

.divider {
    border-left: 1px solid var(--border-color);
}
</style>