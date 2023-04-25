<script setup lang="ts">
import { PropertyType } from '@/data/models';
import { onMounted, ref } from 'vue';

const props = defineProps({
    type: String as () => PropertyType,
    modelValue: String,
    focus: Boolean
})

const inputElem = ref(null)

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
    <input :type="inputType(props.type)" ref="inputElem" class="m-0 p-0 ps-1 bg-light no-border" @input="(e:any) => $emit('update:modelValue', e.target.value)" :value="props.modelValue" placeholder="None.."/>
</template>
