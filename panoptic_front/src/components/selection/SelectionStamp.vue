<script setup lang="ts">
import { computed } from 'vue';
import StampDropdown from '../inputs/StampDropdown.vue';
import wTT from '../tooltips/withToolTip.vue'
import { useProjectStore } from '@/data/projectStore';
import { useDataStore } from '@/data/dataStore';

const data = useDataStore()

const props = defineProps({
    selectedImagesIds: Array<number>
})

const images = computed(() => props.selectedImagesIds.map(id => data.instances[id]))

const emits = defineEmits(['remove:selected', 'stamped'])

</script>

<template>
    <div class="d-flex border rounded p-0 m-0">
        <wTT message="main.menu.remove_selection_tooltip">
            <div class="btn-cls" @click="emits('remove:selected')"><i class="bi bi-x"></i></div>
        </wTT>
        <div class="selection-counter"><StampDropdown :images="images" :no-border="true" :show-number="true" @stamped="emits('stamped')"/></div>
    </div>
</template>

<style scoped>
.border {
    border: 2px solid #007bff !important;
    overflow: hidden;
    white-space: nowrap;
}

.btn-cls {
    padding: 1px 3px;
    border-right: 2px solid #007bff !important;
    cursor: pointer;
    font-size: 12px;
}

.selection-counter {
    cursor: pointer;
    padding: 1px 4px;
    font-size: 12px;
}
</style>