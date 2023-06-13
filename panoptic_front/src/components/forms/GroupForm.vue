<script setup lang="ts">
import { globalStore } from '@/data/store';
import { computed } from 'vue';
import PropertySelection from '../inputs/PropertySelection.vue';


const props = defineProps({
    groupIds: Array<number>
})


const selectedProperties = computed(() => props.groupIds.map(id => globalStore.properties[id]))

</script>

<template>
    <div class="d-flex flex-row">
        <div class="label">Group by</div>
        <div class="bg-medium d-flex flex-row rounded m-0 p-0">
            <template v-for="property, index in selectedProperties">
                <i v-if="index > 0" class="bi bi-chevron-right smaller"></i>
                <div class="btn btn-sm no-border" @click="props.groupIds.splice(index, 1)">{{ property.name }}</div>
            </template>
        </div>
        <div class="btn btn-sm no-border me-1 p-1 hover-light text-secondary" data-bs-toggle="dropdown"
            data-bs-auto-close="true">
            <i class="bi bi-plus"></i>
        </div>
        <div class="dropdown-menu p-0">
            <PropertySelection @select="prop => globalStore.addGrouping(prop.id)" :ignore-ids="props.groupIds" />
        </div>
    </div>
</template>