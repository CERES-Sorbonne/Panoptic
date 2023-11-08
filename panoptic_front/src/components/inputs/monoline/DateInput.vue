
<script setup lang="ts">
import { Image, Property } from '@/data/models';
import { computed } from 'vue';
import { globalStore } from '@/data/store';
import { getImageProperty } from '@/utils/utils';
import StandaloneDateInput from './StandaloneDateInput.vue';


const props = defineProps({
    image: Object as () => Image,
    property: Object as () => Property,
    width: Number
})

const propRef = computed(() => getImageProperty(props.image.id, props.property.id))

function save(date: Date) {
    globalStore.setPropertyValue(props.property.id, props.image, date)
}

</script>

<template>
    <StandaloneDateInput :model-value="propRef.value" @update:model-value="save" :width="props.width"/>
</template>
