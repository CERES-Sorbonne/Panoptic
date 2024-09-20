<script setup lang="ts">
import { Instance, Property, PropertyType } from '@/data/models';
import TextPropInput from './TextPropInput.vue';
import CheckboxPropInput from './CheckboxPropInput.vue';
import DatePropInput from './DatePropInput.vue';
import TagPropInputDropdown from '../tags/TagPropInputDropdown.vue';
import { isTag } from '@/utils/utils';
import ColorPropInput2 from './ColorPropInput2.vue';


const props = defineProps({
    property: Object as () => Property,
    image: Object as () => Instance,
    minHeight: Number,
    width: Number
})

const emits = defineEmits(["update:height"])

</script>

<template>
    <TextPropInput v-if="property.type == PropertyType.string" :min-height="minHeight" ref="inputElems"
        @update:height="h => emits('update:height', h)" :image="props.image" :property="property" :width="props.width" />
    <TextPropInput v-if="property.type == PropertyType.url" :min-height="minHeight" ref="inputElems" :url-mode="true"
        @update:height="h => emits('update:height', h)" :image="props.image" :property="property" :width="props.width" />
    <TextPropInput v-if="property.type == PropertyType.path" :min-height="minHeight" ref="inputElems" 
        @update:height="h => emits('update:height', h)" :image="props.image" :property="property" :width="props.width" />
    <TagPropInputDropdown v-if="isTag(property.type)" :property="property" :image="props.image" :width="props.width"
        :can-create="true" :can-customize="true" :can-delete="true" :can-link="true" :input-id="[0]" :auto-focus="true"
        @update:height="h => emits('update:height', h)" ref="inputElems" />
    <CheckboxPropInput v-if="property.type == PropertyType.checkbox" :min-height="minHeight" ref="inputElems"
        @update:height="h => emits('update:height', h)" :image="props.image" :property="property" :width="props.width" />
    <ColorPropInput2 v-if="property.type == PropertyType.color" :min-height="minHeight" ref="inputElems"
        @update:height="h => emits('update:height', h)" :image="props.image" :property="property" :width="props.width" />

    <TextPropInput v-if="property.type == PropertyType.number" :min-height="minHeight" ref="inputElems"
        @update:height="h => emits('update:height', h)" :image="props.image" :property="property" :width="props.width" />

    <DatePropInput v-if="property.type == PropertyType.date" :min-height="minHeight" ref="inputElems"
        @update:height="h => emits('update:height', h)" :image="props.image" :property="property" :width="props.width" />
</template>