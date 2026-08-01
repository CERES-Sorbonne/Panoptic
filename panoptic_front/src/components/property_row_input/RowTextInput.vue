<script setup lang="ts">
import { ref } from 'vue';
import IconTextInput from '@/components/property_inputs/IconTextInput.vue';
import PropertyIcon from '@/components/properties/PropertyIcon.vue';
import { PropertyType } from '@/data/models';

const props = withDefaults(defineProps<{
    modelValue?: string
    // Property type shown as the icon inside the input. Defaults to the text icon.
    type?: PropertyType
    width?: number
    // Caps how wide the edit popup may grow (it otherwise widens with the text, up to 400px).
    // Used where the input sits in a fixed slot that it must not overflow.
    maxWidth?: number
    height?: number
    teleport?: boolean
    offset?: number
}>(), {
    offset: -24
})

const emits = defineEmits(['update:modelValue', 'focus', 'tab'])

defineExpose({ focus })

const inputElem = ref(null)

function focus() {
    inputElem.value?.focus()
}
</script>

<template>
    <div :style="{ width: props.width ? props.width+0.7 + 'px' : '100%' }">
        <IconTextInput ref="inputElem" :model-value="props.modelValue" :max-width="props.maxWidth ?? 400"
            :teleport="props.teleport" @update:model-value="v => emits('update:modelValue', v)"
            @focus="emits('focus')" @tab="emits('tab')">
            <template #icon>
                <PropertyIcon :type="props.type ?? PropertyType.string" />
            </template>
        </IconTextInput>
    </div>
</template>

<style scoped></style>
