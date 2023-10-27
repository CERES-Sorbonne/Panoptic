<script setup lang="ts">
import { globalStore } from '@/data/store';
import { ref, computed, onMounted, nextTick } from 'vue';
import PropertyIcon from '../properties/PropertyIcon.vue';

const props = defineProps({
    modelValue: Number
})

const property = computed(() => {
    let id = props.modelValue ? props.modelValue : Object.keys(globalStore.properties)[0]
    return globalStore.properties[Number(id)]
})

</script>

<template>
        <div class="text-nowrap m-0 p-0">
            <PropertyIcon :type="property.type" />
            {{ property.name }}
        </div>
</template>