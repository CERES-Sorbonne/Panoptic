<script setup lang="ts">
import { globalStore } from '@/data/store';
import { computed, reactive } from 'vue';
import PropertySelection from '../inputs/PropertySelection.vue';
import { PropertyType, Sort } from '@/data/models';


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

function delSort(index: number) {
    const sort = props.sortList[index]
    if (sort.isGroup) {
        return
    }
    props.sortList.splice(index, 1)
}

</script>

<template>
    <div class="d-flex flex-row sort-form">
        <div class="pt-1 pb-1">Sort:</div>
        <div class="d-flex flex-row m-0 p-0 bg-medium bg ms-1" v-if="sortList.length">
            <template v-for="sort, index in props.sortList">
                <i v-if="index > 0" class="bi bi-chevron-right smaller"></i>
                <div class="me-0 ms-1 ps-1 mt-1 mb-1 pe-1" @click="delSort(index)"
                    :class="sort.isGroup ? 'text-secondary' : '  base-hover '">
                    {{ globalStore.properties[sort.property_id].name }}
                </div>
                <template v-if="sort.isGroup">
                    <template v-if="sort.byGroupSize">
                        <i v-if="sort.ascending" class="bi bi-sort-up-alt sm-btn" @click="sort.byGroupSize = false"></i>
                        <i v-else class="bi bi-sort-down sm-btn" @click="sort.byGroupSize = false"></i>
                    </template>
                    <template v-else>
                        <template v-if="globalStore.properties[sort.property_id].type == PropertyType.number">
                            <i v-if="sort.ascending" class="bi bi-sort-numeric-up sm-btn" @click="sort.byGroupSize = true"></i>
                            <i v-else class="bi bi-sort-numeric-down-alt sm-btn" @click="sort.byGroupSize = true"></i>
                        </template>
                        <template v-else>
                            <i v-if="sort.ascending" class="bi bi-sort-alpha-up sm-btn" @click="sort.byGroupSize = true"></i>
                            <i v-else class="bi bi-sort-alpha-down-alt sm-btn" @click="sort.byGroupSize = true"></i>
                        </template>
                    </template>
                    <!-- <i v-if="sort.byGroupSize" @click="sort.byGroupSize = false" class="bi bi-collection btn btn-sm no-border"></i>
                    <i v-else @click="sort.byGroupSize = true"  class="bi bi-123  btn btn-sm no-border"></i> -->
                </template>
                <!-- <i class="me-1"></i> -->
                <i v-if="sort.ascending" class="bi bi-arrow-up sm-btn" @click="sort.ascending = false"></i>
                <i v-else class="bi bi-arrow-down sm-btn" @click="sort.ascending = true"></i>
            </template>
        </div>
        <div class="hover-light text-secondary m-1" data-bs-toggle="dropdown"
            data-bs-auto-close="true">
            <span class="base-hover plus-btn"><i class="bi bi-plus"></i></span>
        </div>
        <div class="dropdown-menu p-0">
            <PropertySelection @select="prop => addSort(prop)" :ignore-ids="selectedIds" />
        </div>
    </div>
</template>

<style scoped>

.sort-form {
    color: rgb(33, 37, 41);
    font-size: 14px;
}

.bg {
    border-radius: 3px;
}

.plus-btn {
    padding: 4px;
    border-radius: 3px;
}

</style>