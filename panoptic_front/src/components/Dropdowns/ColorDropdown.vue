<script setup lang="ts">
import Dropdown from './Dropdown.vue';
import { useDataStore } from '@/data/dataStore';
import { Colors } from '@/data/models';
import ColorInput from '../property_inputs/ColorInput.vue';
const data = useDataStore()

const props = defineProps<{
    modelValue: number
}>()
const emits = defineEmits(['update:modelValue'])


</script>

<template>
    <Dropdown>
        <template v-slot:button>
            <div :style="{ backgroundColor: Colors[props.modelValue].color }"
                style="height: 20px;width: 20px; border-radius: 5px; cursor: pointer;">
            </div>
        </template>

        <template v-slot:popup="{hide}">
            <div class="main-box pt-1">
                <ColorInput :hide-preview="true" :hide-white="true" :model-value="props.modelValue"
                    @update:model-value="e => {emits('update:modelValue', e); hide();}" />
            </div>
        </template>

    </Dropdown>
</template>

<style scoped>
.main-box {
    width: 100px;
}
</style>