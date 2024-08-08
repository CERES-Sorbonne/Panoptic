
<script setup lang="ts">
import { Instance, Property } from '@/data/models';
import { computed } from 'vue';
import StandaloneDateInput from './StandaloneDateInput.vue';
import { useDataStore } from '@/data/dataStore';

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
    let toSave = undefined
    if(date) {
        toSave = new Date(date).toISOString()
    }
    data.setPropertyValue(props.property.id, props.image, toSave)
}

</script>

<template>
    <StandaloneDateInput :model-value="localValue" @update:model-value="save" :width="props.width" :teleport="true"/>
</template>
