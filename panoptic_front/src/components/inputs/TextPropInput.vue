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
    minHeight: {type: Number, default: 30}

})

const emits = defineEmits({ 'update:height': Number })

const localValue = ref('')

const propRef = computed(() => getImageProperty(props.image.id, props.property.id))

function updateFromStore() {
    localValue.value = propRef.value.value ?? ''
}

onMounted(updateFromStore)
watch(propRef, updateFromStore)
watch(localValue, () => globalStore.setPropertyValue(props.property.id, props.image, localValue.value))

</script>

<template>
    <TextInput :contenteditable="true" tag="div" :no-html="true" v-model="localValue" :width="props.width" @update:height="h => emits('update:height', h)"/>
</template>

<style scoped>

.contenteditable {
    white-space: break-spaces;
    padding-left: 2px;
    padding-right: 2px;
}

</style>
