<script setup lang="ts">
import { onMounted, ref, watch } from 'vue';
import Dropdown from './Dropdown.vue';
import { DateUnit } from '@/data/models';

const props = defineProps<{
    modelValue: DateUnit
}>()

const emits = defineEmits<{
    'update:modelValue': [v: DateUnit]
}>()

const options = Object.values(DateUnit)

function select(option: DateUnit) {
    emits('update:modelValue', option)
}
</script>

<template>
    <Dropdown>
        <template #button><div class="base-hover ps-1 pe-1">{{ props.modelValue }}</div></template>
        <template #popup="{hide}">
            <div class="main">
                <div v-for="option in options" class="base-hover option" @click="select(option); hide();">{{ option }}</div>
            </div>
        </template>
    </Dropdown>
</template>

<style scoped>

.main {
    padding: 5px;
    font-size: 15px;
}

.option {
    padding: 2px 4px;
}

</style>