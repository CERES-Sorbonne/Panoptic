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
    <div class="d-flex b-border">
        <div class="sb" @click="emits('remove:selected')"><i class="bi bi-x"/></div>
        <div class="sb"><StampDropdown :images="images" :no-border="true" :show-number="true" @stamped="emits('stamped')"/></div>
    </div>
</template>

<style scoped>
.b-border {
    border: 1px solid var(--blue);
    overflow: hidden;
    white-space: nowrap;
    border-radius: 3px; 
    align-items: center;
    column-gap: 1px;
    padding: 1px 1px;
}

</style>