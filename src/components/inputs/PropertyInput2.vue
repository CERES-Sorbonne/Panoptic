<script setup lang="ts">
import { PropertyType } from '@/data/models';

const props = defineProps({
    type: String as () => PropertyType,
    modelValue: String
})


function inputType(type: PropertyType) {
    switch (type) {
        case PropertyType.number:
            return 'number'
        case PropertyType.date:
            return 'date'
        case PropertyType.color:
            return 'color'
        case PropertyType.checkbox:
            return 'checkbox'
        default:
            return 'text'
    }
}

</script>


<template>
    <input :type="inputType(props.type)" class="bg-light border border-secondary rounded p-1" @input="(e:any) => $emit('update:modelValue', e.target.value)" />
</template>
