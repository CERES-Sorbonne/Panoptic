
<script setup lang="ts">
import { Instance, Property } from '@/data/models';
import { computed } from 'vue';
import { useProjectStore } from '@/data/projectStore'
import StandaloneDateInput from './StandaloneDateInput.vue';
import { useDataStore } from '@/data/dataStore';

const project = useProjectStore()
const data = useDataStore()

const props = defineProps<{
    image: Instance
    property: Property
    width: number
}>()


const propValue = computed(() => data.instances[props.image.id].properties[props.property.id])

const localValue = computed(() => {
    if(propValue.value) return propValue.value
    return undefined
})


function save(date: Date) {
    const toSave = new Date(date).toISOString()
    console.log(date)
    project.setPropertyValue(props.property.id, props.image, toSave)
}

</script>

<template>
    <StandaloneDateInput :model-value="localValue" @update:model-value="save" :width="props.width" :teleport="true"/>
</template>
