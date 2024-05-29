<script setup lang="ts">
import { computed } from 'vue';
import PropertyIcon from '../properties/PropertyIcon.vue';
import { useDataStore } from '@/data/dataStore';

const data = useDataStore()

const props = defineProps({
    modelValue: Number
})

const property = computed(() => {
    let id = props.modelValue ? props.modelValue : Object.keys(data.properties)[0]
    return data.properties[Number(id)]
})

</script>

<template>
        <div class="text-nowrap m-0 p-0">
            <PropertyIcon :type="property.type" />
            {{ property.name }}
        </div>
</template>