<!-- Wrapper to connect any property input to a value in the database -->
<script setup lang="ts">
import { useDataStore } from '@/data/stores/dataStore';
import { Property } from '@/data/models';
import { InstanceEntry } from '@/data/stores/instanceStore';
import { computed, nextTick, onMounted, ref, watch } from 'vue';

const data = useDataStore()

const props = defineProps<{
    instance: InstanceEntry
    propertyId: number
}>()
const emits = defineEmits([])

defineExpose({
    waitForDbAction
})

const propValue = computed(() => props.instance.properties?.[props.propertyId])
const status = computed(() => props.instance.propertyStatus?.[props.propertyId] ?? 'confirmed')
const localValue = ref(undefined)
const valid = ref(true)

let dbAction: Promise<any> | null = null

async function set(value: any, instance: InstanceEntry) {
    // very important to avoid setting values of old input to new input params
    // creates the crazy UI bug where everythings gets set around
    if (!valid.value) return
    if (JSON.stringify(value) === JSON.stringify(instance.properties?.[props.propertyId])) return
    if (instance === props.instance) localValue.value = value
    dbAction = data.setPropertyValue(props.propertyId, instance, value)
    await dbAction
    dbAction = null
    loadValue()
}

// The setter given to the slot is bound to the instance it was rendered for. Recycled rows keep
// this component and only swap `instance`; an editor of the previous instance that commits late
// (CellTextInput commits a tick after blur) must still write where the user typed, not into the
// instance the row shows now.
const boundSet = computed(() => {
    const instance = props.instance
    return (value: any) => set(value, instance)
})

function loadValue() {
    localValue.value = propValue.value
}

async function forceUpdate() {
    valid.value = false
    await nextTick()
    valid.value = true
}

async function waitForDbAction() {
    if (dbAction) await dbAction
}

onMounted(loadValue)
watch(propValue, loadValue)
watch(() => props.instance.id, forceUpdate)
</script>

<template>
    <template v-if="valid">
        <slot :set="boundSet" :value="localValue" :status="status"></slot>
    </template>
</template>

<style scoped></style>