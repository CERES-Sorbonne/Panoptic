<script setup lang="ts">
import { globalStore } from '@/data/store'
import { computed, onMounted, ref } from 'vue'
import PropertyIcon from '../properties/PropertyIcon.vue'
import { Property, PropertyType } from '@/data/models'

const props = defineProps({
    ignoreIds: Array<number>
})
const emits = defineEmits(['select'])

const searchElem = ref(null)

const propertyFilter = ref('')

const filteredProperties = computed(() => {
    let properties = globalStore.propertyList
    if(props.ignoreIds) {
        properties = properties.filter(p => !props.ignoreIds.includes(p.id))
    }
    return properties.filter(p => p.name.includes(propertyFilter.value))
})

onMounted(() => searchElem.value.focus())

</script>

<template>
    <div>
        <div class="mb-1 ps-2 pe-2"><input class="w-100 bg-light" type="text" ref="searchElem" v-model="propertyFilter" /></div>
        <li v-for="prop in filteredProperties" class="dropdown-item" style="cursor:pointer" @click="emits('select', prop.id)">
            <PropertyIcon :type="prop.type" class="me-2" />
            <a>{{ prop.name }}</a>
        </li>
    </div>
</template>