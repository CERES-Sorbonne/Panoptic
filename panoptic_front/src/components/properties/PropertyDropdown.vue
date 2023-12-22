<script setup lang="ts">
import { Property, PropertyID } from '@/data/models';
import Dropdown from '../dropdowns/Dropdown.vue';
import PropertySelection from '../inputs/PropertySelection.vue';
import { ref } from 'vue';
import PropertyIcon from './PropertyIcon.vue';
import { useStore } from '@/data/store2';

const store = useStore()

const props = defineProps({
    modelValue: Object as () => Property
})

const emits = defineEmits(['update:modelValue'])

const dropdownElem = ref(null)

function select(propId) {
    dropdownElem.value.hide()
    emits('update:modelValue', store.data.properties[propId])
}

</script>

<template>
    <Dropdown ref="dropdownElem" :auto-focus="false">
        <template #button>
            <div class="m-0 base-btn" style="padding: 1px 2px;">
                <PropertyIcon :type="props.modelValue.type" />
                {{ props.modelValue.name }}</div>
        </template>

        <template #popup>
            <div class="p-2">
                <PropertySelection v-model="props.modelValue" @select="select" :ignore-ids="[PropertyID.folders]"/>
            </div>
        </template>
    </Dropdown>
</template>