<script setup lang="ts">
import { globalStore } from '@/data/store';
import { ref, computed, onMounted, nextTick } from 'vue';
import PropertyIcon from '../properties/PropertyIcon.vue';

const props = defineProps({
    modelValue: Number
})

const searchElem = ref(null)
const buttonElem = ref(null)

const hideButton = ref(false)

const propertyFilter = ref('')

const property = computed(() => {
    let id = props.modelValue ? props.modelValue : Object.keys(globalStore.properties)[0]
    return globalStore.properties[Number(id)]
})

const filteredProperties = computed(() => {
    return globalStore.propertyList.filter(p => p.name.includes(propertyFilter.value))
})

onMounted(() => {
    buttonElem.value.addEventListener('show.bs.dropdown', () => {
        nextTick(() => searchElem.value.focus())
    })
})

</script>

<template>
    <div>
        <div class="btn-group">
            <button class="border border-secondary rounded dropdown-toggle p-1 bg-white text-secondary hover-light" type="button" data-bs-toggle="dropdown"
                data-bs-auto-close="true" aria-expanded="false" ref="buttonElem">
                <PropertyIcon :type="property.type" />
                {{ property.name }}
            </button>
            <ul class="dropdown-menu m-0 p-0">
                <input class="small-input m-2 bg-light" type="text" ref="searchElem" v-model="propertyFilter"/>
                <li v-for="prop in filteredProperties" class="dropdown-item" style="cursor:pointer" @click="$emit('update:modelValue', prop.id)">
                    <PropertyIcon :type="prop.type" class="me-2"/>
                    <a>{{ prop.name }}</a>
                </li>
            </ul>
        </div>
    </div>
</template>