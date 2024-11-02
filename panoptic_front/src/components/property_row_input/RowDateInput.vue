<script setup lang="ts">
import Dropdown from '@/components/dropdowns/Dropdown.vue';
import { onMounted, ref, watch } from 'vue';
import DatePreview from '../property_preview/DatePreview.vue';
import DateInput from '../property_inputs/DateInput.vue';

const props = defineProps<{
    modelValue?: string
    width?: number
    height?: number
    noNl?: boolean
    teleport?: boolean
}>()

const emits = defineEmits(['update:modelValue'])

defineExpose({ focus })

const dropdownElem = ref(null)
const previewElem = ref(null)
const localValue = ref<string>(undefined)

function loadValue() {
    localValue.value = props.modelValue
}

function submit(hide) {
    emits('update:modelValue', localValue.value)
    hide()
}

function cancel() {
    loadValue()
}

function focus() {
    if (!dropdownElem.value) return
    dropdownElem.value.show()
}

onMounted(loadValue)
watch(() => props.modelValue, loadValue)


</script>

<template>
    <Dropdown :offset="-20" :no-shadow="false" :teleport="props.teleport" @esc="cancel" @enter="submit" placement="bottom"
        ref="dropdownElem">
        <template v-slot:button>
            <div ref="previewElem" style="padding-left: 0px;">
                <DatePreview :date="props.modelValue" class="row-preview" style="cursor: pointer;"
                    :style="{ width: props.width ? props.width + 'px' : '100%' }" />
            </div>
        </template>
        <template v-slot:popup="{ hide }">
            <div class="p-2">
                <DateInput v-model="localValue" :extended="true" :auto-focus="true" @cancel="cancel(); hide()"
                    @submit="submit(hide)" />
            </div>
        </template>
    </Dropdown>
</template>

<style scoped>
.row-preview {
    font-size: inherit;
}
</style>