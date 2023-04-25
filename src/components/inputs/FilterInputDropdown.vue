<script setup lang="ts">
import { Filter, FilterGroup } from '@/data/models';
import { computed, reactive, ref, watch } from 'vue';
import { globalStore } from '@/data/store';
import SoloFilterInput from './SoloFilterInput.vue';
import FilterGroupInput from './FilterGroupInput.vue';
import * as bootstrap from 'bootstrap'

const props = defineProps({
    modelValue: Object as () => Filter | FilterGroup
})

const emits = defineEmits(['update:modelValue', 'delete'])

const buttonElem = ref(null)

const isGroup = computed(() => props.modelValue.isGroup)
const filter = computed(() => (props.modelValue as Filter))
const filterGroup = computed(() => props.modelValue as FilterGroup)

function close() {
    let dropdown = bootstrap.Dropdown.getOrCreateInstance(buttonElem.value)
    dropdown.hide()
}

function deleteFilter() {
    emits('delete')
    close()
}

watch(() => props.modelValue, () => {
    emits('update:modelValue', props.modelValue)
},{deep: true})

</script>

<template>
    <div class="btn-group">
        <button class="btn btn-sm border rounded bg-white hover-light me-1 dropdown-toggle" type="button" data-bs-toggle="dropdown" data-bs-auto-close="outside"
            aria-expanded="false" ref="buttonElem">
            <span v-if="!isGroup">{{ globalStore.properties[filter.propertyId].name }}: {{ filter.operator }}</span>
            <span v-else>Group <span class="badge bg-medium text-dark me-1">{{ filterGroup.filters.length }}</span></span>
        </button>
        <div class="dropdown-menu m-0 p-0" style="min-width: 0px;">
            <div class="m-0 p-0" v-if="Object.keys(globalStore.properties).length > 0">
                <SoloFilterInput :filter="(props.modelValue as Filter)" v-if="!isGroup" @close="close" @delete="deleteFilter"/>
                <FilterGroupInput :filter="(props.modelValue as FilterGroup)" v-else @delete="deleteFilter"/>
            </div>
            <div class="bg-light text-dark p-1 btn-icon rounded-bottom w-100 text-nowrap" @click="deleteFilter"><i class="bi bi-trash me-1"></i>delete filter</div>
        </div>
    </div>
</template>
