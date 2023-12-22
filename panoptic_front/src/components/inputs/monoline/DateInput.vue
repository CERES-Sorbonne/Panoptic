
<script setup lang="ts">
import { Image, Property } from '@/data/models';
import { computed } from 'vue';
import { useStore } from '@/data/store'
import { getImageProperty } from '@/utils/utils';
import StandaloneDateInput from './StandaloneDateInput.vue';

const store = useStore()
const props = defineProps({
    image: Object as () => Image,
    property: Object as () => Property,
    width: Number
})

const propRef = computed(() => getImageProperty(props.image.id, props.property.id))
const localValue = computed(() => {
    if(propRef.value.value) return new Date(propRef.value.value)
    return undefined
})


function save(date: Date) {
    store.setPropertyValue(props.property.id, props.image, date)
}

</script>

<template>
    <StandaloneDateInput :model-value="localValue" @update:model-value="save" :width="props.width"/>
</template>
