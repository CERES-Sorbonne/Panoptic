<script setup lang="ts">
import { Colors } from '@/data/models';
import 'vue-color-kit/dist/vue-color-kit.css'
const props = defineProps<{
    modelValue?: number
}>()
const emits = defineEmits(['update:modelValue'])

function set(colorId: number) {
    emits('update:modelValue', colorId)
}

</script>

<template>
    <div class="bg-white">
        <div>
            <div v-for="c, index in Colors" class="d-flex flex-row color-option" @click="set(index)"
                :class="props.modelValue == index ? 'selected' : ''">
                <div :style="{ backgroundColor: c.color }" class="color"></div>
                <div class="color-name"> {{ c.name }}</div>
            </div>
            <div class="hr m-1"></div>
            <div class="d-flex flex-row color-option" @click="set(undefined)"
                :class="props.modelValue == undefined ? 'selected' : ''">
            <div :style="{ backgroundColor: '#ffffff' }" class="color"></div>
            <div class="color-name"> None </div>
        </div>
    </div>
    </div>
</template>

<style scoped>
.container {
    padding: 0;
}

.separator {
    background-color: white;
    width: 100%;
    padding-top: 6px;
    border-bottom: 1px solid var(--border-color);
    margin-bottom: 4px;
}

.color-name {
    text-transform: capitalize;
    line-height: 20px;
    color: var(--text-color);
    font-size: 13px;
}

.color {
    width: 20px;
    height: 20px;
    border-radius: 15%;
    border: 1px solid var(--border-color);
    margin-right: 5px;
}

.color-option {
    padding: 3px 5px;
    border-radius: 5px;
    margin: 0 3px;
    cursor: pointer;
    /* background-color: var(--light-grey); */
}

.color-option:hover {
    background-color: var(--light-grey) !important;
}

.selected {
    background-color: rgb(240, 240, 240);
    border-radius: 5px;
}
</style>
