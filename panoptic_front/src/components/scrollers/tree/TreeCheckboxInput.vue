<script setup lang="ts">
// Checkbox property row of a tree cell. No edit mode: the box is the value, clicking the
// frame toggles it.
import { ref } from 'vue'
import TreeCellFrame from './TreeCellFrame.vue'
import { PropertyType } from '@/data/models'

const props = defineProps<{
    modelValue?: boolean
    label?: string
}>()

const emits = defineEmits(['update:modelValue', 'focus', 'blur', 'tab'])

const inputElem = ref(null)

function focus() {
    inputElem.value?.focus()
}

function toggle() {
    // unset rather than false, so the property reads as "no value" when unchecked
    emits('update:modelValue', props.modelValue ? undefined : true)
}

defineExpose({ focus })
</script>

<template>
    <!-- no icon: the box itself is what the property icon would have shown -->
    <TreeCellFrame :type="PropertyType.checkbox" :no-icon="true" @click="toggle">
        <input ref="inputElem" class="box" type="checkbox" :checked="!!props.modelValue" @click.stop="toggle"
            @focus="emits('focus')" @blur="emits('blur')" @keydown.tab.stop.prevent="emits('tab')" /><span
            v-if="props.label" class="label2">{{ props.label }}</span>
    </TreeCellFrame>
</template>

<style scoped>
.box {
    vertical-align: middle;
    margin: 0;
    cursor: pointer;
}

/* the markup joins the two tags directly, so this is the whole gap — no whitespace node */
.label2 {
    margin-left: 3px;
    vertical-align: middle;
}
</style>
