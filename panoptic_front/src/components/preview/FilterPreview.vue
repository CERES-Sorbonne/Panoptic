<script setup lang="ts">
import { availableOperators, Filter, operatorHasInput, PropertyType } from '@/data/models';
import { globalStore } from '@/data/store';
// import { filterData } from '@/utils/filter';
import { computed, watch } from 'vue';
import TagPreview from '../preview/TagPreview.vue';
import PropertyPreview from '../preview/PropertyPreview.vue';
import PropertyInput2 from '../inputs/PropertyInput2.vue';
import PropertyValuePreview from './PropertyValuePreview.vue';

const props = defineProps({
    filter: Object as () => Filter
})

const property = computed(() => globalStore.properties[props.filter.propertyId])

</script>
<template>
    <td class="d-flex hover-light ps-1 overflow-hidden">
        <div class="m-0 p-0 me-2">
            <PropertyPreview v-model="props.filter.propertyId" />
        </div>
    <!-- </td>
    <td> -->
        <div class="m-0 p-0 me-2 text-nowrap">
            {{props.filter.operator}}
        </div>
    <!-- </td>
    <td class="w-100"> -->
        <div class="m-0 p-0 me-2" v-if="operatorHasInput(props.filter.operator)" style="width: 150px;">
            <PropertyValuePreview :property="property" :value="props.filter.value"/>
        </div>
    <!-- </td> -->
    </td>
</template>

<style scoped>

td {
    border-radius: 3px;
    cursor: pointer;
}

</style>