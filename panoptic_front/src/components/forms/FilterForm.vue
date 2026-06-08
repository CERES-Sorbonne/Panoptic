<script setup lang="ts">
import { computed } from 'vue';
import GlobalFilterInputDropdown from '../dropdowns/MainFilterDropdown.vue';
import AddFilterBtn from '../filter/AddFilterBtn.vue';
import { TabManager } from '@/core/TabManager';
import { CollectionManager } from '@/core/CollectionManager';

const props = defineProps<{
    tab: TabManager
    collection?: CollectionManager
}>()

const collection = computed(() => props.collection ?? props.tab.collection)

</script>

<template>
    <div class="d-flex flex-row filter-form align-items-center">
        <div class="pt-1 pb-1">{{ $t("main.menu.filters") }}: </div>
        <GlobalFilterInputDropdown :manager="collection.filterManager" :tab="props.tab"/>

        <AddFilterBtn :manager="collection.filterManager" :group="collection.filterManager.state.filter" class="p-1">
            <span class="base-hover plus-btn text-secondary "><i class="bi bi-plus"></i></span>
        </AddFilterBtn>
    </div>
</template>

<style scoped>

.filter-form {
    color: rgb(33, 37, 41);
    font-size: 14px;
}

.plus-btn {
    padding: 5px 4px;
    border-radius: 2px;
}

</style>