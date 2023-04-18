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
    <div>
        <div class="btn-group">
            <button class="border border-secondary rounded dropdown-toggle p-1 bg-white text-secondary hover-light" type="button" data-bs-toggle="dropdown"
                data-bs-auto-close="true" aria-expanded="false" ref="buttonElem">
                {{ props.modelValue }}
            </button>
            <ul class="dropdown-menu m-0 p-0">
                <li v-for="op in filteredOperators" class="dropdown-item" style="cursor:pointer"
                    @click="$emit('update:modelValue', op)">
                    <a>{{ op }}</a>
                </li>
            </ul>
        </div>
    </div>
</template>