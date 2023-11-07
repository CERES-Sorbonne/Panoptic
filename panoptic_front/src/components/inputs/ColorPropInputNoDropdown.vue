<script setup lang="ts">
import { Colors, Image, Property } from '@/data/models';
import { getImageProperty } from '@/utils/utils';
import { computed } from 'vue';
import { globalStore } from '@/data/store';
import 'vue-color-kit/dist/vue-color-kit.css'
const props = defineProps({
    modelValue: Number,
    width: Number,
    minHeight: { type: Number, default: 30 },
    rounded: Boolean,
    hidePreview: Boolean,
    hideWhite: Boolean

})
const emits = defineEmits(['update:modelValue'])

const color = computed(() => {
    if (props.modelValue == undefined) return 'white'

    let value = Number(props.modelValue)
    if (isNaN(value) || value > 12) return 'gray'
    return Colors[value].color
})

function set(colorId: number) {
    emits('update:modelValue', colorId)
}

</script>

<template>
    <div :style="{ minHeight: props.minHeight + 'px' }" class="container bg-white">
        <div :class="props.rounded ? 'rounded' : ''"
            :style="{ width: props.width + 'px', height: 'calc(100% - 3px)' }">
            <div v-if="!props.hidePreview" :style="{ backgroundColor: color, height: '30px', width: '100%' }">
            </div>

            <div v-if="!props.hidePreview" class="separator"></div>

            <div class="bg-white">
                <div>
                    <div v-for="c, index in Colors" class="d-flex flex-row color-option" @click="set(index)">
                        <div :style="{ backgroundColor: c.color }" class="color"></div>
                        <div class="color-name"> {{ c.name }}</div>
                    </div>
                    <div v-if="!props.hideWhite" class="hr m-1"></div>
                    <div v-if="!props.hideWhite" class="d-flex flex-row color-option" @click="set(undefined)">
                        <div :style="{ backgroundColor: '#ffffff' }" class="color"></div>
                        <div class="color-name"> None </div>
                    </div>
                </div>
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
    background-color: var(--light-grey);
}
</style>
