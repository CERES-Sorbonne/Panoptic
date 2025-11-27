<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import PropertyIcon from '../properties/PropertyIcon.vue'
import { deletedID, useDataStore } from '@/data/dataStore'
import { PropertyType, Property } from '@/data/models'

const data = useDataStore()

interface Props {
    ignoreIds?: number[]
    // The component accepts an array of acceptable types for filtering
    acceptableTypes?: PropertyType[] | null
    // modelValue is included as PropertySelection is often used within a dropdown 
    // that uses v-model internally, though it's not strictly used for input here.
    modelValue?: Property | null
}

const props = defineProps<Props>()
const emits = defineEmits<{
    (e: 'select', id: number): void
}>()

const searchElem = ref<HTMLInputElement | null>(null)
const propertyFilter = ref('')

const filteredProperties = computed(() => {
    let properties = data.propertyList.filter(p => p.id !== deletedID)

    if (props.ignoreIds) {
        properties = properties.filter(p => !props.ignoreIds?.includes(p.id))
    }

    // Apply acceptableTypes filter
    if (props.acceptableTypes && props.acceptableTypes.length > 0) {
        properties = properties.filter(p => props.acceptableTypes?.includes(p.type))
    }

    return properties.filter(p => p.name.toLocaleLowerCase().includes(propertyFilter.value.toLocaleLowerCase()))
})

onMounted(() => searchElem.value?.focus())
</script>

<template>
    <div class="p-1">
        <div class="mb-1 ps-2 pe-2">
            <input class="w-100 bg-light" type="text" ref="searchElem" v-model="propertyFilter" />
        </div>
        <div 
            v-for="prop in filteredProperties" 
            class="p-1 base-hover text-black" 
            style="cursor:pointer" 
            @click="emits('select', prop.id)"
        >
            <PropertyIcon :type="prop.type" class="me-2" />
            <a>{{ prop.name }}</a>
        </div>
    </div>
</template>