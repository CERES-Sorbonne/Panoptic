<script setup lang="ts">
import { ref, onMounted, watch, nextTick } from 'vue'
import SelectDropdown, { SelectOption } from '../dropdowns/SelectDropdown.vue';
import { keyState } from '@/data/keyState';
import { useDataStore } from '@/data/dataStore';
import { objValues } from '@/utils/utils';

const data = useDataStore()
const props = defineProps<{
    modelValue?: number
}>()
const emits = defineEmits(['update:modelValue'])

const inputElem = ref(null)

const mapOptions = ref<SelectOption[]>([])
const localMap = ref()




async function updateMaps() {
    await useDataStore().loadMaps()
    // 1. First, rebuild the options list so we have something to fall back to
    mapOptions.value = objValues(data.maps).map(m => ({
        value: m.id,
        label: m.id + ': ' + m.source + '.' + m.name,
        icon: 'geo'
    }))

    // 2. Determine what the "next" value should be based on current props
    let nextValue = props.modelValue

    // 3. Validation: If the value from props doesn't exist in our data, invalidate it
    if (nextValue && !data.maps[nextValue]) {
        nextValue = null
    }

    // 4. Fallback: If we have no value (or it was invalidated) but we have options, pick the first
    if (!nextValue && mapOptions.value.length) {
        console.log('Defaulting to first available map', { old: props.modelValue, new: mapOptions.value[0].value })
        nextValue = mapOptions.value[0].value as number
    }

    // 5. Final Sync: Update local state and notify parent only if changed
    if (nextValue !== localMap.value) {
        localMap.value = nextValue
        emits('update:modelValue', nextValue)
    }
}

// updateModes()
watch(() => props.modelValue, (val) => localMap.value = val)
watch(() => data.maps, () => updateMaps())
watch(localMap, (val) => emits('update:modelValue', val))

onMounted(() => {
    localMap.value = props.modelValue
    updateMaps()
})

keyState.ctrlF.on(() => inputElem.value?.focus())

</script>

<template>
    <div class="cont3">
        <SelectDropdown :options="mapOptions" v-model="localMap" :placeholder="$t('map.select_map')" :no-border="true" :teleport="true"/>
    </div>
    <!-- <div class="nofound">No Point Maps found</div> -->
</template>

<style scoped>
.cont3 {
    display: flex;
    gap: 4px;
    align-items: center;
    border-radius: 3px;
    width: 100%;
    /* overflow: hidden; */
}

.nofound {
    border: 1px solid var(--border-color);
    border-radius: 3px;
    padding: 0 4px;
    font-size: 14px;
    color: #999;
}
</style>