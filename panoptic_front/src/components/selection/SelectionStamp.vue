<script setup lang="ts">
import { computed } from 'vue';
import StampDropdown from '../inputs/StampDropdown.vue';
import { globalStore } from '@/data/store';



const props = defineProps({
    selectedImagesIds: Array<number>
})

const images = computed(() => props.selectedImagesIds.map(id => globalStore.images[id]))

const emits = defineEmits(['remove:selected'])

</script>

<template>
    <div class="d-flex border rounded p-0 m-0">
        <div class="btn-cls" @click="emits('remove:selected')"><i class="bi bi-x"></i></div>
        <div class="selection-counter"><StampDropdown :images="images" :no-border="true" :show-number="true"/></div>
    </div>
</template>

<style scoped>
.border {
    border: 2px solid var(--border-color) !important;
    overflow: hidden;
}

.btn-cls {
    padding: 1px 3px;
    border-right: 2px solid var(--border-color);
    cursor: pointer;
    font-size: 12px;
}

.selection-counter {
    cursor: pointer;
    padding: 1px 4px;
    font-size: 12px;
}
</style>