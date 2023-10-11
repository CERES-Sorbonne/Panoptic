<script setup lang="ts">
import { Image, Property, PropertyType, isTag } from '@/data/models';
import TextPropInput from './TextPropInput.vue';
import TagPropInput from './TagPropInput.vue';
import CheckboxPropInput from './CheckboxPropInput.vue';
import ColorPropInput from './ColorPropInput.vue';
import NumberPropInput from './NumberPropInput.vue';
import DatePropInput from './DatePropInput.vue';


const props = defineProps({
    property: Object as () => Property,
    image: Object as () => Image,
    minHeight: Number,
    width: Number
})

const emits = defineEmits(["update:height"])

</script>

<template>
    <TextPropInput v-if="property.type == PropertyType.string" :min-height="minHeight" ref="inputElems"
        @update:height="h => emits('update:height', h)" :image="props.image" :property="property" :width="props.width" />
    <TextPropInput v-if="property.type == PropertyType.url" :min-height="minHeight" ref="inputElems"
        @update:height="h => emits('update:height', h)" :image="props.image" :property="property" :width="props.width" />
    <TextPropInput v-if="property.type == PropertyType.path" :min-height="minHeight" ref="inputElems"
        @update:height="h => emits('update:height', h)" :image="props.image" :property="property" :width="props.width" />
    <TagPropInput v-if="isTag(property.type)" :property="property" :image="props.image" ref="inputElems"
        @update:height="h => emits('update:height', h)" :width="props.width" :input-id="[0]" />
    <CheckboxPropInput v-if="property.type == PropertyType.checkbox" :min-height="minHeight" ref="inputElems"
        @update:height="h => emits('update:height', h)" :image="props.image" :property="property" :width="props.width" />
    <ColorPropInput v-if="property.type == PropertyType.color" :min-height="minHeight" ref="inputElems"
        @update:height="h => emits('update:height', h)" :image="props.image" :property="property" :width="props.width" />

    <NumberPropInput v-if="property.type == PropertyType.number" :min-height="minHeight" ref="inputElems"
        @update:height="h => emits('update:height', h)" :image="props.image" :property="property" :width="props.width" />

    <DatePropInput v-if="property.type == PropertyType.date" :min-height="minHeight" ref="inputElems"
        @update:height="h => emits('update:height', h)" :image="props.image" :property="property" :width="props.width" />
</template>