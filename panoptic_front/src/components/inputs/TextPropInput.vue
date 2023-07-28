<script setup lang="ts">
import { Image, Property } from '@/data/models';
import { getImageProperty } from '@/utils/utils';
import { computed, onMounted, ref, watch } from 'vue';
import TextInput from './TextInput.vue';
import { globalStore } from '@/data/store';

const props = defineProps({
    property: Object as () => Property,
    image: Object as () => Image,
    noNl: {
        type: Boolean,
        default: false,
    },
    width: Number,
    minHeight: { type: Number, default: 30 }

})
const emits = defineEmits({ 'update:height': Number })

const localValue = ref('')
const elem = ref(null)
// const inputElem = computed(() => elem.value.inputElem)

const propRef = computed(() => getImageProperty(props.image.id, props.property.id))

function focus() {
    elem.value.focus()
}

function updateFromStore() {
    localValue.value = propRef.value.value ?? ''
}

onMounted(updateFromStore)
watch(propRef, updateFromStore)
watch(localValue, () => globalStore.setPropertyValue(props.property.id, props.image, localValue.value))


defineExpose({
    localValue,
    // inputElem
    focus
})


</script>

<template>
    <div>
        <TextInput  class="input" :contenteditable="true" tag="div" :no-html="true" v-model="localValue" :width="props.width"
            @update:height="h => emits('update:height', h)" ref="elem" :min-height="props.minHeight"/>
    </div>
</template>

<style scoped>
.input {
    margin-top: 2px;
}
</style>
