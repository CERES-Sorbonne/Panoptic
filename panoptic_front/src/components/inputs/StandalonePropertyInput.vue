<script setup lang="ts">
import { PropertyType } from '@/data/models';
import { onMounted, ref, watch } from 'vue';
import PropertyIcon from '../properties/PropertyIcon.vue';

const props = defineProps({
    type: String as () => PropertyType,
    modelValue: [String, Boolean],
    focus: Boolean
})

const emits = defineEmits(['update:modelValue'])

const inputElem = ref(null)
const localValue = ref(null)

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

onMounted(() => localValue.value = props.modelValue)
watch(localValue, () => emits('update:modelValue', localValue.value))

</script>


<template>
    <div class="d-flex flex-row">
        <PropertyIcon :type="props.type" class="me-1" />
        <input :type="inputType(props.type)" ref="inputElem" class="m-0 p-0 ps-1 bg-light no-border" style="width: 100%;"
        v-model="localValue" placeholder="None.." />
    </div>
    
</template>
