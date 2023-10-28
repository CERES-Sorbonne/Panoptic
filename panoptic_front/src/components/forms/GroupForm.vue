<script setup lang="ts">
import { globalStore } from '@/data/store';
import { computed, onMounted } from 'vue';
import PropertySelection from '../inputs/PropertySelection.vue';
import { Sort } from '@/data/models';


const props = defineProps({
    groupIds: Array<number>,
    sorts: Array<Sort>,
    isLoading: Boolean
})


const selectedProperties = computed(() => props.groupIds.map(id => globalStore.properties[id]))

onMounted(() => {
    if (props.groupIds) {
        props.groupIds.forEach(id => globalStore.addGrouping(id))
    }
})

</script>

<template>
    <div class="d-flex flex-row">
        <div class="label">Group by</div>
        <div class="bg-medium d-flex flex-row rounded m-0 p-0">
            <template v-for="property, index in selectedProperties">
                <i v-if="index > 0" class="bi bi-chevron-right smaller"></i>
                <div class="btn btn-sm no-border" @click="globalStore.delGrouping(property.id)">
                    {{ property.name }}
                </div>
            </template>
            <i  v-if="props.isLoading" class="spinner-grow spinner-grow-sm loading ms-1"></i>
        </div>
        <div class="dropdown">
            <div class="me-1 mt-1 hover-light text-secondary" data-bs-toggle="dropdown"
                data-bs-auto-close="true" v-show="!props.isLoading">
                <i class="bi bi-plus"></i>
            </div>
            <div class="dropdown-menu p-0">
                <PropertySelection @select="prop => globalStore.addGrouping(prop)" :ignore-ids="props.groupIds" />
            </div>
        </div>

    </div>
</template>

<style scoped>
.loading {
    background-color: rgb(171, 171, 171);
    margin-top: 7px;
    margin-right: 5px;
    margin-left: -3px;
}
</style>