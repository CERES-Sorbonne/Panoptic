<script setup lang="ts">
import { availableOperators, Filter, operatorHasInput, PropertyType } from '@/data/models';
import { globalStore } from '@/data/store';
// import { filterData } from '@/utils/filter';
import { computed, watch } from 'vue';
import OperatorDropdown from './OperatorDropdown.vue';
import PropertyDropdown from './PropertyDropdown.vue';
import PropertyInput2 from './PropertyInput2.vue';
import TagDropdown from './TagDropdown.vue';

const props = defineProps({
    filter: Object as () => Filter
})

const property = computed(() => globalStore.properties[props.filter.propertyId])


watch(() => props.filter.propertyId, (id) => {
    let type = globalStore.properties[id].type
    props.filter.operator = availableOperators(type)[0]
    props.filter.value = undefined
})

watch(() => props.filter.operator, (operator) => {
    if(!operatorHasInput(operator)) {
        props.filter.value = undefined
    }
})

</script>
<template>
    <td>
        <div class="me-2">
            <PropertyDropdown v-model="props.filter.propertyId" />
        </div>
    </td>
    <td>
        <div class="me-2">
            <OperatorDropdown :property-id="props.filter.propertyId" v-model="props.filter.operator" />
        </div>
    </td>
    <td class="w-100">
        <div class="me-2" v-if="operatorHasInput(props.filter.operator)">
            <TagDropdown v-if="property.type == PropertyType.multi_tags || property.type == PropertyType.tag" v-model="filter.value"
                :property-id="props.filter.propertyId" />
            <PropertyInput2 v-else :type="property.type" v-model="filter.value"/>
        </div>
    </td>
</template>