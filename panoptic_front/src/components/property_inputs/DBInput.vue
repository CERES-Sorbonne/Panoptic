<!-- Wrapper to connect any property input to a value in the database -->
<script setup lang="ts">
import { useDataStore } from '@/data/dataStore';
import { Instance, Property } from '@/data/models';
import { computed, nextTick, onMounted, ref, watch } from 'vue';

const data = useDataStore()

const props = defineProps<{
    instance: Instance
    propertyId: number
}>()
const emits = defineEmits([])

const propValue = computed(() => data.instances[props.instance.id].properties[props.propertyId])
const localValue = ref(undefined)
const valid = ref(true)

async function set(value: any) {
    // very important to avoid settings values of old input to new input params
    // creates the crazy UI bug where everythings gets set around
    if (!valid.value) return
    if (JSON.stringify(value) === JSON.stringify(propValue.value)) return
    localValue.value = value
    await data.setPropertyValue(props.propertyId, props.instance, value)
    loadValue()
}

function loadValue() {
    localValue.value = propValue.value
}

onMounted(loadValue)
watch(propValue, loadValue)
watch(props, async () => {
    valid.value = false
    await nextTick()
    valid.value = true
})
</script>

<template>
    <template v-if="valid">
        <slot :set="set" :value="localValue"></slot>
    </template>
</template>

<style scoped></style>