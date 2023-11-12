<script setup lang="ts">
import { Colors, Image, Property } from '@/data/models';
import { getImageProperty } from '@/utils/utils';
import { computed, onMounted, ref, watch } from 'vue';
import { globalStore } from '@/data/store';
import 'vue-color-kit/dist/vue-color-kit.css'
import * as bootstrap from 'bootstrap'
import Dropdown from '../dropdowns/Dropdown.vue';

const props = defineProps({
    modelValue: Number,
    width: Number,
    minHeight: { type: Number, default: 30 },
    rounded: Boolean

})
const emits = defineEmits({ 'update:height': Number, 'update:modelValue': undefined, 'blur': undefined })

const dropdownElem = ref(null)

const color = computed(() => {
    if (props.modelValue == undefined) return 'white'

    let value = Number(props.modelValue)
    if (isNaN(value) || value > 12) return 'gray'
    return Colors[value].color
})

function set(color: number) {
    emits('update:modelValue', color)
    dropdownElem.value.hide()

}

defineExpose({
    focus
})

</script>

<template>
    <Dropdown ref="dropdownElem" @hide="emits('blur')">
        <template #button>
            <!-- <input type="color" v-model="localValue" :style="{
            width: props.width+ 'px',
        }" ref="elem" @focusin="isFocus = true" @focusout="isFocus = false"/> -->
            <div :class="props.rounded ? 'rounded' : ''"
                :style="{ width: props.width + 'px', backgroundColor: color, height: '20px', cursor: 'pointer' }">
                <span v-if="props.modelValue == undefined" class="text-secondary">None...</span>
            </div>
        </template>

        <template #popup>
            <div class="p-1">
                <div v-for="c, index in Colors" class="d-flex flex-row color-option" @click="set(index)">
                    <div :style="{ backgroundColor: c.color }" class="color"></div>
                    <div class="color-name"> {{ c.name }}</div>
                </div>
                <div class="hr m-1"></div>
                <div class="d-flex flex-row color-option" @click="set(undefined)">
                    <div :style="{ backgroundColor: '#ffffff' }" class="color"></div>
                    <div class="color-name"> None </div>
                </div>
            </div>
        </template>
    </Dropdown>
</template>

<style scoped>
.container {
    padding: 0;
    cursor: pointer;
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
