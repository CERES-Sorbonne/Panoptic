<script setup lang="ts">
import { defineProps, defineEmits, ref, onMounted, watch } from 'vue'
import SelectDropdown, { SelectOption } from '../dropdowns/SelectDropdown.vue';
import { useDataStore } from '@/data/dataStore';
import { VectorType } from '@/data/models';

const data = useDataStore()
const props = defineProps<{
    modelValue?: VectorType
    source?: string
    filterBySource?: boolean
    width?: number
}>()
const emits = defineEmits(['update:modelValue'])

const vectorOptions = ref<SelectOption[]>([])
const selectedVector = ref(props.modelValue.id)

function vectorName(vectorType: VectorType) {
    return '' + vectorType.id + ' ' + vectorType.source + '.' + Object.keys(vectorType.params).filter(k => vectorType.params[k]).map(k => k + '_' + vectorType.params[k]).join('_')
}

function updateVectorOptions() {
    let vectors = data.vectorTypes
    
    // Filter by source if needed
    if (props.filterBySource && props.source) {
        vectors = vectors.filter(v => v.source == props.source)
    }
    
    vectorOptions.value = vectors.map(v => ({
        value: v.id,
        label: vectorName(v),
    }))

    if(!selectedVector.value && vectorOptions.value.length) {
        selectedVector.value = vectorOptions.value[0].value as number
    }
}

watch(() => data.vectorTypes, () => updateVectorOptions())
watch(selectedVector, (val) => emits('update:modelValue', data.vectorTypes.find(v => v.id == val)))
watch(() => props.modelValue, (val) => selectedVector.value = val.id)
watch(() => props.source, () => updateVectorOptions())

onMounted(() => {
    updateVectorOptions()
})

</script>

<template>
    <div class="vector-dropdown-cont">
        <SelectDropdown 
            :options="vectorOptions" 
            v-model="selectedVector" 
            placeholder="Select vector type" 
            class="bg-white"
            :size="14"
            :width="props.width"
        />
    </div>
</template>

<style scoped>
.vector-dropdown-cont {
    display: flex;
    /* gap: 4px; */
    align-items: center;
    border-radius: 3px;
    /* overflow: hidden; */
}
</style>