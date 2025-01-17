<script setup lang="ts">

const props = defineProps<{
    modelValue: string
    options: string[]
    langKeys?: string[]
}>()

const emits = defineEmits(['update:modelValue'])

function set(value: string) {
    emits('update:modelValue', value)
}
</script>

<template>
    <div class="d-flex text-center main">
        <template v-for="option, index in props.options">
            <div v-if="index" class="sep"></div>
            <div class="option flex-grow-1" :class="props.modelValue == option ? 'selected' : ''" @click="set(option)">
                <span v-if="props.langKeys && props.langKeys[index]"> {{ $t(props.langKeys[index]) }} </span>
                <span v-else>{{ option }}</span>
            </div>
        </template>
    </div>
</template>

<style scoped>

.main {
    border-bottom: 1px solid var(--border-color);
}
.sep {
    border-left: 1px solid var(--border-color);
}

.option {
    font-size: 13px;
    line-height: 26px;
    background-color: var(--tab-grey);
    /* border-bottom: 1px solid var(--border-color); */
    cursor: pointer;
}

.selected {
    /* border-bottom: 1px solid white; */
    background-color: white;
}
</style>