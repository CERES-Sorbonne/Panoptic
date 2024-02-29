<script setup lang="ts">
// import { filterData } from '@/utils/filter';
import { computed, watch } from 'vue';
import PropertyValuePreview from './PropertyValuePreview.vue';
import { operatorHasInput, Filter } from '@/core/FilterManager'
import { useProjectStore } from '@/data/projectStore';

const store = useProjectStore()

const props = defineProps({
    filter: Object as () => Filter
})

const property = computed(() => store.data.properties[props.filter.propertyId])

</script>
<template>
    <td class="d-flex bb ps-1 overflow-hidden">
        <!-- <div class="m-0 p-0 me-2">
            <PropertyPreview v-model="props.filter.propertyId" />
        </div> -->
        <!-- </td>
    <td> -->
        <div class="m-0 p-0 me-2 text-nowrap">
            {{ $t('modals.filters.operators.' + props.filter.operator) }}
        </div>
        <!-- </td>
    <td class="w-100"> -->
        <div class="m-0 p-0 me-2" v-if="operatorHasInput(props.filter.operator)" style="width: 150px;">
            <PropertyValuePreview :property="property" :value="props.filter.value" />
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