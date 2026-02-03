<script setup lang="ts">
import { useProjectStore } from '@/data/projectStore'
import { computed } from 'vue';
import wTT from '../tooltips/withToolTip.vue'
import PropertyDropdown from '../dropdowns/PropertyDropdown.vue';
import { SortManager, SortDirection } from '@/core/SortManager';
import { useDataStore } from '@/data/dataStore';
const data = useDataStore()
interface Sort {
    propertyId: number
    direction: SortDirection
}

const props = defineProps({
    manager: SortManager
})

const sortList = computed(() => {
    return props.manager.state.sortBy.map(s => {
        const res: Sort = {
            propertyId: s,
            direction: props.manager.state.options[s].direction
        }
        return res
    })
})

const selectedIds = computed(() => sortList.value.map(p => p.propertyId))

function addSort(propertyId: number) {
    props.manager.setSort(propertyId)
    props.manager.update(true)
}

function delSort(propertyId: number) {
    props.manager.delSort(propertyId)
    props.manager.update(true)
}

function setOrder(propertyId: number, direction: SortDirection) {
    props.manager.setSort(propertyId, {direction})
    props.manager.update(true)
}



</script>

<template>
    <div class="d-flex flex-row sort-form align-items-center">
        <div class="me-1">{{$t("main.menu.sort.title")}}: </div>
        <div class="d-flex flex-row m-0 p-0 bg-medium bg align-items-center" v-if="sortList.length">
            <template v-for="sort, index in sortList">
                <i v-if="index > 0" class="bi bi-chevron-right smaller"></i>
                <div class="bbw" @click="delSort(sort.propertyId)">
                    {{ data.properties[sort.propertyId].name }}
                </div>
                <wTT v-if="sort.direction == SortDirection.Ascending" message="main.menu.sort.order_asc">
                    <i class="bi bi-arrow-up bbw" @click="setOrder(sort.propertyId, SortDirection.Descending)"></i>
                </wTT>
                <wTT v-else message="main.menu.sort.order_desc">
                    <i class="bi bi-arrow-down bbw" @click="setOrder(sort.propertyId, SortDirection.Ascending)"></i>
                </wTT>
            </template>
        </div>
        <PropertyDropdown :group-ids="selectedIds" @select="prop => addSort(prop)" />
    </div>
</template>

<style scoped>

.sort-form {
    color: rgb(33, 37, 41);
    font-size: 14px;
}

.bg {
    border-radius: 2px;
    overflow: hidden;
    height: 26px;
}

.bbw {
    padding: 2.5px 4px;
    cursor: pointer;
}

.bbw:hover {
    background-color: rgb(240, 240, 240);
}

.plus-btn {
    padding: 5px 4px;
    border-radius: 2px;
}

</style>