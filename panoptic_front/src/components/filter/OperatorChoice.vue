<script setup lang="ts">
import { computed } from 'vue';
import Dropdown from '../dropdowns/Dropdown.vue';
import { FilterOperator, availableOperators } from '@/core/FilterManager';
import { useDataStore } from '@/data/dataStore';

const data = useDataStore()
const props = defineProps<{
    propertyId: number,
    modelValue: FilterOperator,
    disabled?: boolean
}>()

const emits = defineEmits(['hide', 'update:modelValue'])

const property = computed(() => {
    return data.properties[props.propertyId]
})

const filteredOperators = computed(() => {
    return availableOperators(property.value.type)
})

async function select(op: FilterOperator) {
    emits('update:modelValue', op)
}
</script>

<template>
    <Dropdown @hide="emits('hide')">
        <template #button>
            <div class="text-nowrap" :class="(props.disabled ? '' : 'dropdown-toggle hover-light button-like')"
                :disabled="props.disabled">
                <span>{{ $t('modals.filters.operators.' + props.modelValue) }}</span>
            </div>
        </template>
        <template #popup="{hide}">

            <div class="m-0 p-1">
                <div v-for="op in filteredOperators" class="hover-light p-1 rounded" style="cursor:pointer"
                    @click="select(op); hide()">
                    <a>{{ $t('modals.filters.operators.' + op) }}</a>
                </div>
            </div>
        </template>

    </Dropdown>
</template>

<style scoped>
.button-like {
    border-radius: 3px;
    cursor: pointer;
    padding-right: 3px;
    padding-left: 3px;
}
</style>