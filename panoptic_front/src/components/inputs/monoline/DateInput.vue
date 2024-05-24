
<script setup lang="ts">
import { Image, Property } from '@/data/models';
import { computed, watch } from 'vue';
import { useProjectStore } from '@/data/projectStore'
import { getImageProperty } from '@/utils/utils';
import StandaloneDateInput from './StandaloneDateInput.vue';

const store = useProjectStore()
const props = defineProps({
    image: Object as () => Image,
    property: Object as () => Property,
    width: Number
})

const propRef = computed(() => getImageProperty(props.image.id, props.property.id))
const localValue = computed(() => {
    if(propRef.value.value) return propRef.value.value
    return undefined
})


function save(date: Date) {
    const toSave = new Date(date).toISOString()
    console.log(date)
    store.setPropertyValue(props.property.id, props.image, toSave)
}

</script>

<template>
    <StandaloneDateInput :model-value="localValue" @update:model-value="save" :width="props.width"/>
</template>
