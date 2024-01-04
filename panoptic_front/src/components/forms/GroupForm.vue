<script setup lang="ts">

import { useProjectStore } from '@/data/projectStore'
import { computed, onMounted } from 'vue';
import PropertyDropdown from '../dropdowns/PropertyDropdown.vue';
import { GroupManager, GroupOption, GroupSortType } from '@/core/GroupManager';
import { SortDirection } from '@/core/SortManager';
import wTT from '../tooltips/withToolTip.vue';
import { PropertyType } from '@/data/models';
import GroupOptionDropdown from '../dropdowns/GroupOptionDropdown.vue';
import { NumberOptions } from 'vue-i18n';
const store = useProjectStore()


const props = defineProps({
    groupIds: Array<number>,
    isLoading: Boolean,
    manager: GroupManager
})

function add(id: number) {
    props.manager.setGroupOption(id)
    props.manager.update(true)
}

function del(id: number) {
    props.manager.delGroupOption(id)
    props.manager.update(true)
}

function setDirection(propertyId: number, value: SortDirection) {
    props.manager.setGroupOption(propertyId, {direction: value})
    props.manager.sortGroups(true)
}

function setSortType(propertyId: number, value: GroupSortType) {
    props.manager.setGroupOption(propertyId, {type: value})
    props.manager.sortGroups(true)
}

function updateGroupOption(propertyId: number, option: GroupOption) {
    props.manager.setGroupOption(propertyId, option)
    props.manager.update(true)
}

const selectedProperties = computed(() => props.manager.state.groupBy.map(id => store.data.properties[id]))
const groups = computed(() => {
    const res: {option: GroupOption, property}[] = []
    props.manager.state.groupBy.forEach(pId => {
        res.push({
            option: props.manager.state.options[pId],
            property: store.data.properties[pId]
        })
    })
    return res
})

</script>

<template>
    <div class="d-flex flex-row group-form">
        <div class="pt-1 pb-1">{{ $t('main.menu.groupby') }}: </div>
        <div class="bg-medium bg d-flex flex-row m-0 ms-1 p-0  align-items-center" v-if="selectedProperties.length">
            <template v-for="group, index in groups">
                <i v-if="index > 0" class="bi bi-chevron-right smaller"></i>
                <div class="base-hover m-1 ps-1 pe-1" @click="del(group.property.id)">
                    {{ group.property.name }}
                </div>
                <wTT v-if="group.option.type == GroupSortType.Size" message="main.menu.sort.group_order_nb_tooltip">
                    <i v-if="group.option.direction == SortDirection.Ascending" class="bi bi-sort-up-alt sm-btn" @click="setSortType(group.property.id, GroupSortType.Property)"></i>
                    <i v-else class="bi bi-sort-down sm-btn" @click="setSortType(group.property.id, GroupSortType.Property)"></i>
                </wTT>
                <wTT v-else message="main.menu.sort.group_order_az_tooltip">
                    <template v-if="group.property.type == PropertyType.number">
                        <i v-if="group.option.direction == SortDirection.Ascending" class="bi bi-sort-numeric-up sm-btn" @click="setSortType(group.property.id, GroupSortType.Size)"></i>
                        <i v-else class="bi bi-sort-numeric-down-alt sm-btn" @click="setSortType(group.property.id, GroupSortType.Size)"></i>
                    </template>
                    <template v-else>
                        <i v-if="group.option.direction == SortDirection.Ascending" class="bi bi-sort-alpha-up sm-btn" @click="setSortType(group.property.id, GroupSortType.Size)"></i>
                        <i v-else class="bi bi-sort-alpha-down-alt sm-btn" @click="setSortType(group.property.id, GroupSortType.Size)"></i>
                    </template>
                </wTT>
                <wTT v-if="group.option.direction == SortDirection.Ascending" message="main.menu.sort.order_asc">
                    <i class="bi bi-arrow-up sm-btn" @click="setDirection(group.property.id, SortDirection.Descending)"></i>
                </wTT>
                <wTT v-else message="main.menu.sort.order_desc">
                    <i class="bi bi-arrow-down sm-btn" @click="setDirection(group.property.id, SortDirection.Ascending)"></i>
                </wTT>
                <div v-if="group.property.type == PropertyType.date" class="sm-btn"><GroupOptionDropdown :option="group.option" @change="e => updateGroupOption(group.property.id, e)"/></div>
            </template>
            <i v-if="props.isLoading" class="spinner-grow spinner-grow-sm loading ms-1"></i>
        </div>
        <PropertyDropdown :group-ids="props.groupIds" @select="prop => add(prop)" />

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
</style>