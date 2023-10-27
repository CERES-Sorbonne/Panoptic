<script setup lang="ts">
import { availableOperators, FilterOperator } from '@/data/models';
import { globalStore } from '@/data/store';
import { ref, computed } from 'vue';

const props = defineProps({
    propertyId: { type: Number, required: true },
    modelValue: String as () => FilterOperator,
    disabled: Boolean
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
        <div class="text-nowrap" :class="(props.disabled ? '' : 'dropdown-toggle hover-light button-like')"
            data-bs-toggle="dropdown" data-bs-auto-close="true" aria-expanded="false" ref="buttonElem" :disabled="props.disabled">
            <span>{{ props.modelValue }}</span>
        </div>
        <ul class="dropdown-menu m-0 p-1">
            <li v-for="op in filteredOperators" class="hover-light p-1 rounded" style="cursor:pointer"
                @click="$emit('update:modelValue', op)">
                <a>{{ op }}</a>
            </li>
        </ul>
    </div>
</template>

<style scoped>

.button-like {
    border-radius: 3px;
    cursor: pointer;
    padding-right: 3px;
    padding-left: 3px;
}

</style>