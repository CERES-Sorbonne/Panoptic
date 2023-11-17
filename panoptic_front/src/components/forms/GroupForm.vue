<script setup lang="ts">
import { globalStore } from '@/data/store';
import { computed, onMounted } from 'vue';
import PropertySelection from '../inputs/PropertySelection.vue';
import { Sort } from '@/data/models';
import Dropdown from '../dropdowns/Dropdown.vue';
import PropertyDropdown from '../dropdowns/PropertyDropdown.vue';


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
        <div class="pt-1 pb-1">{{ $t('main.menu.groupby') }}</div>
        <div class="bg-medium bg d-flex flex-row m-0 ms-1 p-0" v-if="selectedProperties.length">
            <template v-for="property, index in selectedProperties">
                <i v-if="index > 0" class="bi bi-chevron-right smaller"></i>
                <div class="base-hover m-1 ps-1 pe-1" @click="globalStore.delGrouping(property.id)">
                    {{ property.name }}
                </div>
            </template>
            <i v-if="props.isLoading" class="spinner-grow spinner-grow-sm loading ms-1"></i>
        </div>
        <PropertyDropdown :group-ids="props.groupIds" @select="prop => globalStore.addGrouping(prop)"/>

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