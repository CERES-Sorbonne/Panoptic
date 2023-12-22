<script setup lang="ts">
import { useStore } from '@/data/store2'
import Dropdown from './Dropdown.vue';
import PropertySelection from '../inputs/PropertySelection.vue';
import { ref } from 'vue';

const props = defineProps({
    groupIds: Array<number>
})

const emits = defineEmits(['select'])
const dropdownElem = ref(null)
</script>

<template>
    <Dropdown ref="dropdownElem" :auto-focus="false">
        <template #button>
            <div class="text-secondary p-1">
                <span class="base-hover plus-btn"><i class="bi bi-plus"></i></span>
            </div>
        </template>

        <template #popup>
            <div class="p-1">
                <PropertySelection @select="prop => {emits('select', prop); dropdownElem.hide()}" :ignore-ids="props.groupIds" />
            </div>
        </template>


    </Dropdown>
</template>

<style scoped>
.plus-btn {
    padding: 4px !important;
    border-radius: 3px !important;
}
</style>