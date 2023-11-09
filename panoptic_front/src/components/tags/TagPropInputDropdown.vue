<script setup lang="ts">
import { Image, Property } from '@/data/models';
import TagInputDropdown from './TagInputDropdown.vue';
import { nextTick, onMounted, ref, watch } from 'vue';
import { arrayEqual, computedPropValue } from '@/utils/utils';
import { globalStore } from '@/data/store';

const props = defineProps({
    property: Object as () => Property,
    image: Object as () => Image,
    excluded: Array<number>,
    canCreate: Boolean,
    canCustomize: Boolean,
    canLink: Boolean,
    canDelete: Boolean,
    autoFocus: Boolean,
    noWrap: Boolean,
    minHeight: Number,
    width: Number,
})
const emits = defineEmits(['update:height'])
const inputElem = ref(null)
const localValue = ref([])

const propValue = computedPropValue(props.property, props.image)


function updateLocal() {
    localValue.value.length = 0
    if (Array.isArray(propValue.value)) {
        localValue.value.push(...propValue.value)
    }
    onResize()
}

function save() {
    if (arrayEqual(localValue.value, propValue.value ?? [])) return

    globalStore.setPropertyValue(props.property.id, props.image, localValue.value)
}

async function onResize() {
    await nextTick()
    if (!inputElem.value) {
        return
    }
    const newH = inputElem.value.getHeight()
    emits('update:height', newH)
}

onMounted(updateLocal)
watch(propValue, updateLocal)
watch(localValue, save)
watch(() => props.minHeight, onResize)
watch(() => props.width, onResize)
</script>

<template>
    <TagInputDropdown :style="{minHeight: (props.minHeight ? props.minHeight + 'px' : '0'), width: (props.width? props.width+'px': '100%')}" :property="props.property" v-model="localValue" :excluded="props.excluded"
        :can-create="props.canCreate" :can-customize="props.canCustomize" :can-link="props.canLink"
        :can-delete="props.canDelete" :auto-focus="props.autoFocus" :no-wrap="props.noWrap" ref="inputElem" />
</template>