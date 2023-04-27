<script setup lang="ts">
import { FilterGroup, FilterOperator } from '@/data/models';
import { reactive, watch } from 'vue';
import FilterGroupInput from './FilterGroupInput.vue';
import { globalStore } from '@/data/store';

const props = defineProps({
    modelValue: Object as () => FilterGroup
})

const emits = defineEmits(['update:modelValue'])

watch(() => props.modelValue, () => {
    emits('update:modelValue', props.modelValue)
},{deep: true})

</script>

<template>
    <div class="btn-group">
        <button class="btn btn-sm border rounded bg-white hover-light me-1 dropdown-toggle" type="button" data-bs-toggle="dropdown" data-bs-auto-close="outside"
            aria-expanded="false">
            <span class="badge bg-medium text-dark me-1">{{ props.modelValue.filters.length }}</span>Filters
        </button>
        <div class="dropdown-menu m-0 p-0" aria-labelledby="defaultDropdown">
            <div class="m-1 p-0" v-if="Object.keys(globalStore.properties).length > 0">
                <FilterGroupInput :filter="props.modelValue" />
            </div>
        </div>
    </div>
</template>
