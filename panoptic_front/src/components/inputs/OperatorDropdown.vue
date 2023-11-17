<script setup lang="ts">
import { availableOperators, FilterOperator } from '@/data/models';
import { globalStore } from '@/data/store';
import { ref, computed, nextTick } from 'vue';
import Dropdown from '../dropdowns/Dropdown.vue';

const props = defineProps({
    propertyId: { type: Number, required: true },
    modelValue: String as () => FilterOperator,
    disabled: Boolean,
    parent: HTMLElement
})

const emits = defineEmits(['hide', 'update:modelValue'])

const dropdownElem = ref(null)

const property = computed(() => {
    return globalStore.properties[props.propertyId]
})

const filteredOperators = computed(() => {
    return availableOperators(property.value.type)
})

async function select(op: FilterOperator) {
    emits('update:modelValue', op)
    // await nextTick()
    dropdownElem.value.hide()
}
</script>

<template>
    <Dropdown @hide="emits('hide')" ref="dropdownElem" :parent="props.parent">
        <template #button>
            <div class="text-nowrap" :class="(props.disabled ? '' : 'dropdown-toggle hover-light button-like')"
                :disabled="props.disabled">
                <span>{{ $t('modals.filters.operators.' + props.modelValue) }}</span>
            </div>
        </template>
        <template #popup>

            <div class="m-0 p-1">
                <div v-for="op in filteredOperators" class="hover-light p-1 rounded" style="cursor:pointer"
                    @click="select(op)">
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