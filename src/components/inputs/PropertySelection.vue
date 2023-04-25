<script setup lang="ts">
import { globalStore } from '@/data/store'
import { computed, ref } from 'vue'
import PropertyIcon from '../properties/PropertyIcon.vue'


const searchElem = ref(null)

const propertyFilter = ref('')

const filteredProperties = computed(() => {
    return globalStore.propertyList.filter(p => p.name.includes(propertyFilter.value))
})


</script>

<template>
    <div>
        <input class=" m-2 bg-light" type="text" ref="searchElem" v-model="propertyFilter" />
        <li v-for="prop in filteredProperties" class="dropdown-item" style="cursor:pointer" @click="$emit('select', prop)">
            <PropertyIcon :type="prop.type" class="me-2" />
            <a>{{ prop.name }}</a>
        </li>
    </div>
</template>