<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
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
const localMap = ref(props.modelValue)




function updateMaps() {
    mapOptions.value = objValues(data.maps).map(m => ({
        value: m.id,
        label: m.id + ': ' + m.source + '.' + m.name,
        icon: 'geo'
    }))
    if(localMap.value && !data.maps[localMap.value]) {
        localMap.value = null
    }
    if (!localMap.value && mapOptions.value.length) {
        localMap.value = (mapOptions.value[0].value) as number
    }
    emits('update:modelValue', localMap.value)
}

// updateModes()

watch(() => data.maps, () => updateMaps())
watch(localMap, (val) => emits('update:modelValue', val))
watch(() => props.modelValue, (val) => localMap.value = val)

onMounted(() => {
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