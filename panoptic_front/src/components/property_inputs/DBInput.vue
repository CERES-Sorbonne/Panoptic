<!-- Wrapper to connect any property input to a value in the database -->
<script setup lang="ts">
import { useDataStore } from '@/data/dataStore';
import { Instance, Property } from '@/data/models';
import { computed, onMounted, ref, watch } from 'vue';

const data = useDataStore()

const props = defineProps<{
    instance: Instance
    propertyId: number
}>()
const emits = defineEmits([])

const propValue = computed(() => data.instances[props.instance.id].properties[props.propertyId])
const localValue = ref(undefined)

async function set(value: any) {
    if(value === propValue.value) return
    localValue.value = value
    await data.setPropertyValue(props.propertyId, props.instance, value)
    loadValue()
}

function loadValue() {
    localValue.value = propValue.value
}

onMounted(loadValue)
watch(propValue, loadValue)
</script>

<template>
  <slot :set="set" :value="localValue"></slot>
</template>

<style scoped>
</style>