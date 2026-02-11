<script setup lang="ts">
import { ref, watch, onMounted, nextTick } from 'vue'

const props = defineProps<{
    modelValue: string,
    focus?: boolean
}>()
const emits = defineEmits(['update:modelValue'])

const localValue = ref(props.modelValue)
const inputElem = ref(null)
const isFocus = ref(false)

function reset() {
    emits('update:modelValue', '')
    if(props.focus) {
        nextTick(() => inputElem.value.focus())
    }
}

onMounted(() => {
    localValue.value = props.modelValue
    if (props.focus) {
        nextTick(() => inputElem.value.focus())
    }


})
watch(props, () => localValue.value = props.modelValue)
watch(localValue, (val) => emits('update:modelValue', val))
</script>

<template>
    <div class="cont3">
        <div class="input-field d-flex items-align-center" :class="{ focus: isFocus }">
            <input class="text-input2" type="text" v-model="localValue" @focusin="isFocus = true" ref="inputElem"
                @focusout="isFocus = false" />
            <div style="width: 22px;"><i v-if="props.modelValue.length" class="bi bi-x sb" @click="reset" /></div>
        </div>
    </div>
</template>

<style scoped>
.cont3 {
    display: flex;
    gap: 4px;
    align-items: center;
    border-radius: 3px;
    overflow: hidden;
}

.input-field {
    height: 26px;
    border: 1px solid var(--border-color, #ccc);
    background-color: var(--grey, #f8f8f8);
    border-radius: 3px;
    transition: border-color 0.2s, box-shadow 0.2s;
}

.text-input2 {
    height: 24px;
    border: none;
    background-color: transparent;
    outline: none;
}

.input-field:hover {
    border-color: #999;
}

.input-field.focus {
    border-color: var(--blue);
}
</style>