<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import PropertyIcon from '../properties/PropertyIcon.vue'
import { deletedID, useDataStore } from '@/data/dataStore';

const data = useDataStore()

const props = defineProps({
    ignoreIds: Array<number>
})
const emits = defineEmits(['select'])

const searchElem = ref(null)

const propertyFilter = ref('')

const filteredProperties = computed(() => {
    let properties = data.propertyList.filter(p => p.id != deletedID)
    if(props.ignoreIds) {
        properties = properties.filter(p => !props.ignoreIds.includes(p.id))
    }
    // properties = properties.filter(p =>  p.id != PropertyID.id)
    return properties.filter(p => p.name.toLocaleLowerCase().includes(propertyFilter.value.toLocaleLowerCase()))
})

onMounted(() => searchElem.value.focus())

</script>

<template>
    <div class="p-1">
        <div class="mb-1 ps-2 pe-2"><input class="w-100 bg-light" type="text" ref="searchElem" v-model="propertyFilter" /></div>
        <div v-for="prop in filteredProperties" class="p-1 base-hover text-black" style="cursor:pointer" @click="emits('select', prop.id)">
            <PropertyIcon :type="prop.type" class="me-2" />
            <a>{{ prop.name }}</a>
        </div>
    </div>
</template>