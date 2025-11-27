<script setup lang="ts">
import { ref } from 'vue'
import { Property, PropertyID, PropertyType } from '@/data/models'
import Dropdown from '../dropdowns/Dropdown.vue'
import PropertySelection from '../inputs/PropertySelection.vue'
import PropertyIcon from './PropertyIcon.vue'
import { useDataStore } from '@/data/dataStore'

const data = useDataStore()

interface Props {
    modelValue: Property | null
    acceptableTypes?: PropertyType[]
}

const props = withDefaults(defineProps<Props>(), {
    modelValue: null,
    acceptableTypes: null
})

const emits = defineEmits<{
    (e: 'update:modelValue', value: Property): void
}>()

const dropdownElem = ref(null)

function select(propId: number): void {
    const selectedProp: Property = data.properties[propId]
    
    dropdownElem.value?.hide()
    emits('update:modelValue', selectedProp)
}
</script>

---

<template>
    <Dropdown ref="dropdownElem" :auto-focus="false">
        <template #button>
            <div class="m-0 bb" style="white-space: nowrap">
                <span v-if="props.modelValue">
                    <PropertyIcon :type="props.modelValue.type" />
                    {{ props.modelValue.name }}
                </span>
                <span v-else class="text-muted">
                    {{ $t('dropdown.property.select')}}
                </span>
            </div>
        </template>

        <template #popup>
            <div class="p-2">
                <PropertySelection 
                    :model-value="props.modelValue" 
                    @select="select" 
                    :ignore-ids="[PropertyID.folders]"
                    :acceptable-types="props.acceptableTypes" 
                />
            </div>
        </template>
    </Dropdown>
</template>