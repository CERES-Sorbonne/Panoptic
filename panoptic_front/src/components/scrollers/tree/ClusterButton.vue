<script setup lang="ts">
import { computed, ref } from 'vue';


const props = defineProps({
    modelValue: Number
})

const emits = defineEmits(['update:modelValue'])

const inputWidht = computed(() => 10 + String(props.modelValue).length * 6)

</script>

<template>
    <div class="bt d-flex">
        <b class="bi bi-magic h6"></b>
        <input @click.stop="" type="number" :value="props.modelValue" :style="{ width: inputWidht + 'px' }"
            @input="v => emits('update:modelValue', Number((v.target as any).value))" />
    </div>
</template>

<style scoped>
.bt {
    background-color: rgb(186, 90, 184);
    height: 20px;
    font-size: 12px;
    border-radius: 5px;
    padding-top: 1px;
    padding-left: 3px;
    color: white;
}

.bt:hover {
    color: rgb(235, 209, 30);
    /* color: yellow; */
}

input {
    border: none !important;
    height: 14px;
    margin-top: 2px;
    margin-left: 2px;
    margin-right: 2px;
    font-size: 12px !important;
    color: rgb(96, 96, 96);
    /* margin-bottom: 2px; */
}
</style>