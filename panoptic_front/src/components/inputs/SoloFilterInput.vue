<script setup lang="ts">
import { availableOperators, Filter, FilterOperator, operatorHasInput, PropertyType } from '@/data/models';
import { globalStore } from '@/data/store';
// import { filterData } from '@/utils/filter';
import { computed, watch } from 'vue';
import OperatorDropdown from './OperatorDropdown.vue';
import PropertyDropdown from './PropertyDropdown.vue';
import PropertyInput2 from './PropertyInput2.vue';
import TagDropdown from './TagDropdown.vue';
import TagInput2 from './TagInput2.vue';

const props = defineProps({
    filter: Object as () => Filter
})

const emits = defineEmits(['close', 'delete'])

const property = computed(() => globalStore.properties[props.filter.propertyId])

const filteredOperators = computed(() => {
    return availableOperators(property.value.type)
})

function selectOperator(operator: FilterOperator) {
    if (!operatorHasInput(operator)) {
        emits('close')
    }
    props.filter.operator = operator
}

function deleteFilter() {
    emits('delete')
}

watch(() => props.filter.propertyId, (id) => {
    let type = globalStore.properties[id].type
    props.filter.operator = availableOperators(type)[0]
    props.filter.value = undefined
})

watch(() => props.filter.operator, (operator) => {
    if (!operatorHasInput(operator)) {
        props.filter.value = undefined
        emits('close')
    }
})

</script>
<template>
    <div v-if="!operatorHasInput(props.filter.operator)">
        <div class="me-1 p-1 w-100">
            <ul class="list-unstyled mb-0 text-nowrap" style="cursor: pointer;">
                <li class="hover-light ps-2 pe-1 mb-2 rounded" v-for="op in filteredOperators" style="cursor:pointer"
                    @click="selectOperator(op)">
                    <a>{{ op }}</a>
                </li>
            </ul>
        </div>
    </div>
    <div v-else>
        <span class="float-end m-1 btn-icon" @click="emits('delete')"><i class="bi bi-trash"></i></span>
        <OperatorDropdown v-model="props.filter.operator" :property-id="props.filter.propertyId" class="w-100" />
        
        <div v-if="operatorHasInput(props.filter.operator)">
            <div v-if="property.type == PropertyType.multi_tags || property.type == PropertyType.tag">
                <TagInput2 v-model="props.filter.value" :property-id="property.id" :focus="true"/>
            </div>
            <div v-else class="p-1">
                <PropertyInput2 :type="property.type" v-model="filter.value" :focus="true" />
            </div>
        </div>
    </div>
</template>