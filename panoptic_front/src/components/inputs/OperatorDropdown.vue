<script setup lang="ts">
import { availableOperators, FilterOperator } from '@/data/models';
import { globalStore } from '@/data/store';
import { ref, computed } from 'vue';

const props = defineProps({
    propertyId: { type: Number, required: true },
    modelValue: String as () => FilterOperator
})

const buttonElem = ref(null)

const property = computed(() => {
    return globalStore.properties[props.propertyId]
})

const filteredOperators = computed(() => {
    return availableOperators(property.value.type)
})
</script>

<template>
    <div class="m-0 p-0">
        <div class="btn btn-sm no-border rounded dropdown-toggle bg-white hover-light" type="button"
            data-bs-toggle="dropdown" data-bs-auto-close="true" aria-expanded="false" ref="buttonElem">
            {{ props.modelValue }}
        </div>
        <ul class="dropdown-menu m-0 p-1">
            <li v-for="op in filteredOperators" class="hover-light p-1 rounded" style="cursor:pointer"
                @click="$emit('update:modelValue', op)">
                <a>{{ op }}</a>
            </li>
        </ul>
    </div>
</template>