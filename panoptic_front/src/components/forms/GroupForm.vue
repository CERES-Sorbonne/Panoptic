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
    <div class="d-flex flex-row group-form">
        <div class="pt-1 pb-1">Group:</div>
        <div class="bg-medium bg d-flex flex-row m-0 ms-1 p-0" v-if="selectedProperties.length">
            <template v-for="property, index in selectedProperties">
                <i v-if="index > 0" class="bi bi-chevron-right smaller"></i>
                <div class="base-hover m-1 ps-1 pe-1" @click="globalStore.delGrouping(property.id)">
                    {{ property.name }}
                </div>
            </template>
            <i v-if="props.isLoading" class="spinner-grow spinner-grow-sm loading ms-1"></i>
        </div>
        <div class="dropdown">
            <div class="text-secondary p-1" data-bs-toggle="dropdown" data-bs-auto-close="true">
                <span class="base-hover plus-btn"><i class="bi bi-plus"></i></span>
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

.group-form {
    color: rgb(33, 37, 41);
    font-size: 14px;
}

.bg {

    border-radius: 3px;
}

.plus-btn {
    padding: 4px !important;
    border-radius: 3px !important;
}
</style>