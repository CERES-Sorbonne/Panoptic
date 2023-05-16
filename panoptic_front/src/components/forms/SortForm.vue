<script setup lang="ts">
import { globalStore } from '@/data/store';
import { computed } from 'vue';
import PropertySelection from '../inputs/PropertySelection.vue';
import { Sort } from '@/data/models';


const props = defineProps({
    sortList: Array<Sort>
})

const selectedIds = computed(() => props.sortList.map(p => p.property_id))

function addSort(property_id: number) {
    props.sortList.push({
        property_id: property_id,
        ascending: true
    })
}

</script>

<template>
    <div class="d-flex flex-row">
        <div class="label">Sort</div>
        <div class="bg-medium d-flex flex-row rounded m-0 p-0">
            <template v-for="sort, index in props.sortList">
                <i v-if="index > 0" class="bi bi-chevron-right smaller"></i>
                <div class="btn btn-sm no-border me-0 pe-0" @click="props.sortList.splice(index, 1)">
                    {{ globalStore.properties[sort.property_id].name }}
                </div>
                <i v-if="sort.ascending" class="bi bi-arrow-up btn btn-sm no-border" @click="sort.ascending = false"></i>
                <i v-else="sort.ascending" class="bi bi-arrow-down btn btn-sm no-border" @click="sort.ascending = true"></i>
            </template>
        </div>
        <div class="btn btn-sm no-border me-1 p-1 hover-light text-secondary" data-bs-toggle="dropdown"
            data-bs-auto-close="true">
            <i class="bi bi-plus"></i>
        </div>
        <div class="dropdown-menu p-0">
            <PropertySelection @select="prop => addSort(prop.id)" :ignore-ids="selectedIds" />
        </div>
    </div>
</template>