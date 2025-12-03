<script setup lang="ts">
import { defineProps, defineEmits, ref, onMounted, watch } from 'vue'
import SelectDropdown, { SelectOption } from '../dropdowns/SelectDropdown.vue';
import { keyState } from '@/data/keyState';
import { useDataStore } from '@/data/dataStore';
import { objValues } from '@/utils/utils';
import { PointData } from '@/mixins/mapview/useMapLogic';

const data = useDataStore()
const props = defineProps<{
    modelValue?: number
}>()
const emits = defineEmits(['update:modelValue'])

const inputElem = ref(null)

const modeOptions = ref<SelectOption[]>([])
const mode = ref(props.modelValue)




function updateModes() {
    modeOptions.value = objValues(data.maps).map(m => ({
        value: m.id,
        label: m.id + ': ' + m.source + '.' + m.name,
        icon: 'geo'
    }))

    if (!mode.value && modeOptions.value.length) {
        mode.value = (modeOptions.value[0].value) as number
        console.log('chose mode', mode.value)
    }
    
    emits('update:modelValue', mode.value)
}

// updateModes()

watch(() => data.maps, () => updateModes())
watch(mode, (val) => emits('update:modelValue', val))
watch(() => props.modelValue, (val) => mode.value = val)

onMounted(() => {
    updateModes()
})

keyState.ctrlF.on(() => inputElem.value?.focus())

</script>

<template>
    <div class="cont3">
        <SelectDropdown :options="modeOptions" v-model="mode" :placeholder="$t('map.select_map')" :no-border="true" :teleport="true"/>
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