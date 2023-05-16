<script setup lang="ts">
import { Filter, FilterGroup, FilterOperator, PropertyType, operatorHasInput } from '@/data/models';
import { computed, reactive, ref, watch } from 'vue';
import { globalStore } from '@/data/store';
import SoloFilterInput from './SoloFilterInput.vue';
import FilterGroupInput from './FilterGroupInput.vue';
import * as bootstrap from 'bootstrap'
import TagBadge from '../TagTree/TagBadge.vue';

const props = defineProps({
    modelValue: Object as () => Filter | FilterGroup
})

const emits = defineEmits(['update:modelValue', 'delete'])

const buttonElem = ref(null)

const isGroup = computed(() => props.modelValue.isGroup)
const filter = computed(() => (props.modelValue as Filter))
const filterGroup = computed(() => props.modelValue as FilterGroup)
const property = computed(() => {
    if (isGroup.value) {
        return
    }
    return globalStore.properties[filter.value.propertyId]
})

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
}, { deep: true })

</script>

<template>
    <div class="btn btn-sm border rounded bg-white hover-light me-1 dropdown-toggle overflow-hidden text-truncate" type="button" data-bs-toggle="dropdown"
        data-bs-auto-close="outside" aria-expanded="false" ref="buttonElem"
        style="max-width: 200px;">
        <span v-if="!isGroup">
            {{ globalStore.properties[filter.propertyId].name }}:
            <span v-if="!operatorHasInput(filter.operator)">{{ filter.operator }}</span>
            <span v-else-if="property.type == PropertyType.tag || property.type == PropertyType.multi_tags">
                <span v-for="tagId in filter.value">
                    <TagBadge :tag="globalStore.tags[property.id][tagId].value" />
                </span>
            </span>
            <span v-else>{{ filter.value }}</span>
        </span>
        <span v-else>Group <span class="badge bg-medium text-dark me-1">{{ filterGroup.filters.length }}</span></span>
    </div>
    <div class="dropdown-menu m-0 p-0" style="min-width: 0px; max-width: 200px;">
        <div class="m-0 p-0" v-if="Object.keys(globalStore.properties).length > 0">
            <SoloFilterInput :filter="(props.modelValue as Filter)" v-if="!isGroup" @close="close" @delete="deleteFilter" />
            <FilterGroupInput :filter="(props.modelValue as FilterGroup)" v-else @delete="deleteFilter" />
        </div>
        <div class="bg-light text-dark p-1 btn-icon rounded-bottom w-100 text-nowrap" @click="deleteFilter"><i
                class="bi bi-trash me-1"></i>delete filter</div>
    </div>
</template>
