<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue';
import PropertyIcon from '../properties/PropertyIcon.vue';
import { useProjectStore } from '@/data/projectStore';

const store = useProjectStore()

const props = defineProps({
    modelValue: Number
})

const property = computed(() => {
    let id = props.modelValue ? props.modelValue : Object.keys(store.data.properties)[0]
    return store.data.properties[Number(id)]
})

</script>

<template>
        <div class="text-nowrap m-0 p-0">
            <PropertyIcon :type="property.type" />
            {{ property.name }}
        </div>
</template>