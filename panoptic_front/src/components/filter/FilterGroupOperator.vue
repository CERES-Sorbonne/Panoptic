<script setup lang="ts">
import { FilterOperator } from '@/core/FilterManager';
import Dropdown from '../dropdowns/Dropdown.vue';


const props = defineProps<{
    modelValue: FilterOperator
}>()

const emits = defineEmits(['update:modelValue'])

function update(op: FilterOperator) {
    emits('update:modelValue', op)
}
</script>

<template>
    <Dropdown>
        <template #button>
            <div class="p-0 hover-light ps-1 bb" style="width: 50px;">
                <span class="">{{ $t('modals.filters.' + props.modelValue) }}</span>
            </div>
        </template>
        <template #popup="{ hide }">
            <div class="ps-2 pt-1 pb-1 pe-2" @click="hide">
                <div class="base-btn" @click="update(FilterOperator.and)">
                    {{ $t('modals.filters.and') }}
                </div>
                <hr class="m-0 p-0 mt-1 mb-1" />
                <div class="base-btn" @click="update(FilterOperator.or)">
                    {{ $t('modals.filters.or') }}
                </div>
            </div>
        </template>
    </Dropdown>
</template>

<style scoped></style>