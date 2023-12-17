<script setup lang="ts">
import GlobalFilterInputDropdown from '../inputs/GlobalFilterInputDropdown.vue';
import FilterDropdown from '../dropdowns/FilterDropdown.vue';
import { FilterManager } from '@/core/FilterManager';

const props = defineProps({
    manager: FilterManager
})

</script>

<template>
    <div class="d-flex flex-row filter-form">
        <div class="pt-1 pb-1">{{ $t("main.menu.filters") }}: </div>
        <GlobalFilterInputDropdown :model-value="props.manager.filter" :manager="props.manager"/>
      
        <FilterDropdown :manager="props.manager" class="p-1">
            <span class="base-hover plus-btn text-secondary "><i class="bi bi-plus"></i></span>
        </FilterDropdown>
    </div>
</template>

<style scoped>

.filter-form {
    color: rgb(33, 37, 41);
    font-size: 14px;
}

.plus-btn {
    padding: 4px;
    border-radius: 3px;
}

</style>