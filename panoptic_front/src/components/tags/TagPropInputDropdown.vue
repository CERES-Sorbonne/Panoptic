<script setup lang="ts">

/**
 * Input for Tags connected directly to an image property
 * Selecting tags in this input directly affects the database
 */

import TagInputDropdown from './TagInputDropdown.vue';
import { computed, nextTick, onMounted, ref, toRefs, watch } from 'vue';
import { arrayEqual } from '@/utils/utils';
import { Instance, Property } from '@/data/models';
import { useDataStore } from '@/data/dataStore';
import { Exception } from 'sass';

const data = useDataStore()

const props = defineProps({
    property: Object as () => Property,
    image: Object as () => Instance,
    excluded: Array<number>,
    canCreate: Boolean,
    canCustomize: Boolean,
    canLink: Boolean,
    canDelete: Boolean,
    autoFocus: Boolean,
    noWrap: Boolean,
    minHeight: Number,
    width: Number,
    teleport: Boolean
})
const emits = defineEmits(['update:height'])
const inputElem = ref(null)
const localValue = ref([])

const refProps = toRefs(props)
// const propValue = computed(() => computedPropValue(props.property, props.image))
const propValue = computed(() => data.instances[props.image.id]?.properties[props.property.id])

function updateLocal() {
    localValue.value.length = 0
    if (Array.isArray(propValue.value)) {
        localValue.value.push(...propValue.value)
    }
    onResize()
}

function save() {
    // console.log(localValue.value, propValue.value)
    if (arrayEqual(localValue.value, (propValue.value ?? []))) return

    data.setPropertyValue(props.property.id, props.image, localValue.value)
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
// watch(localValue, save)
watch(() => props.minHeight, onResize)
watch(() => props.width, onResize)
</script>

<template>
    <TagInputDropdown :style="{minHeight: (props.minHeight ? props.minHeight + 'px' : '0'), width: (props.width? props.width+'px': '100%')}" :property="props.property" v-model="localValue" :excluded="props.excluded"
        :can-create="props.canCreate" :can-customize="props.canCustomize" :can-link="props.canLink"
        :can-delete="props.canDelete" :auto-focus="props.autoFocus" :no-wrap="props.noWrap" :teleport="props.teleport" ref="inputElem" 
        @hide="save"/>
</template>