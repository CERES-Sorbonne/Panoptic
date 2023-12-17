<script setup lang="ts">
import { globalStore } from '@/data/store';
import { computed } from 'vue';
import wTT from '../tooltips/withToolTip.vue'
import PropertyDropdown from '../dropdowns/PropertyDropdown.vue';
import { SortManager, SortDirection } from '@/core/SortManager';

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
    <div class="d-flex flex-row sort-form">
        <div class="pt-1 pb-1">{{$t("main.menu.sort.title")}}</div>
        <div class="d-flex flex-row m-0 p-0 bg-medium bg ms-1 align-items-center" v-if="sortList.length">
            <template v-for="sort, index in sortList">
                <i v-if="index > 0" class="bi bi-chevron-right smaller"></i>
                <!-- <div class="me-0 ms-1 ps-1 mt-1 mb-1 pe-1" @click="delSort(sort.property_id)"
                    :class="sort.isGroup ? 'text-secondary' : '  base-hover '">
                    {{ globalStore.properties[sort.property_id].name }}
                </div> -->
                <div class="me-0 ms-1 ps-1 mt-1 mb-1 pe-1 base-hover" @click="delSort(sort.propertyId)">
                    {{ globalStore.properties[sort.propertyId].name }}
                </div>
                <!-- <template v-if="sort.isGroup">
                    <wTT v-if="sort.byGroupSize" message="main.menu.sort.group_order_nb_tooltip">
                        <i v-if="sort.ascending" class="bi bi-sort-up-alt sm-btn" @click="sort.byGroupSize = false"></i>
                        <i v-else class="bi bi-sort-down sm-btn" @click="sort.byGroupSize = false"></i>
                    </wTT>
                    <wTT v-else message="main.menu.sort.group_order_az_tooltip">
                        <template v-if="globalStore.properties[sort.property_id].type == PropertyType.number">
                            <i v-if="sort.ascending" class="bi bi-sort-numeric-up sm-btn" @click="sort.byGroupSize = true"></i>
                            <i v-else class="bi bi-sort-numeric-down-alt sm-btn" @click="sort.byGroupSize = true"></i>
                        </template>
                        <template v-else>
                            <i v-if="sort.ascending" class="bi bi-sort-alpha-up sm-btn" @click="sort.byGroupSize = true"></i>
                            <i v-else class="bi bi-sort-alpha-down-alt sm-btn" @click="sort.byGroupSize = true"></i>
                        </template>
                    </wTT>
                </template> -->
                <!-- <i class="me-1"></i> -->
                <wTT v-if="sort.direction == SortDirection.Ascending" message="main.menu.sort.order_asc">
                    <i class="bi bi-arrow-up sm-btn" @click="setOrder(sort.propertyId, SortDirection.Descending)"></i>
                </wTT>
                <wTT v-else message="main.menu.sort.order_desc">
                    <i class="bi bi-arrow-down sm-btn" @click="setOrder(sort.propertyId, SortDirection.Ascending)"></i>
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
    border-radius: 3px;
}

.plus-btn {
    padding: 4px;
    border-radius: 3px;
}

</style>