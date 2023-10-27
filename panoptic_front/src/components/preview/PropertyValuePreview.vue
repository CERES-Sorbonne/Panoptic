<script setup lang="ts">
import { Property, PropertyMode, PropertyType } from '@/data/models';
import TagPreview from './TagPreview.vue';

const props = defineProps({
    value: Object as () => any,
    property: Object as () => Property
})
</script>

<template>
    <template v-if="value != undefined">
        <div v-if="props.property.type == PropertyType._ahash">
            {{ props.value }}
        </div>
        <div v-if="props.property.type == PropertyType._folders">
            {{ props.value }}
        </div>
        <div v-if="props.property.type == PropertyType._sha1">
            {{ props.value }}
        </div>
        <div v-if="props.property.type == PropertyType.checkbox">
            <i v-if="props.value"  class="bi bi-square"></i>
            <i v-else class="bi bi-check-square"></i>
        </div>
        <div v-if="props.property.type == PropertyType.color" :style="{backgroundColor: (props.value as string)}">
        </div>
        <div v-if="props.property.type == PropertyType.date">
            {{ props.value }}
        </div>
        <div v-if="props.property.type == PropertyType.image_link">
        </div>
        <div v-if="props.property.type == PropertyType.multi_tags">
            <TagPreview :property-id="props.property.id" :value="props.value" />
        </div>
        <div v-if="props.property.type == PropertyType.number">
            {{ props.value }}
        </div>
        <div v-if="props.property.type == PropertyType.path">
            {{ props.value }}
        </div>
        <div v-if="props.property.type == PropertyType.string">
            {{ props.value }}
        </div>
        <div v-if="props.property.type == PropertyType.tag">
            <TagPreview :property-id="props.property.id" :value="props.value" />
        </div>
        <div v-if="props.property.type == PropertyType.url">
            {{ props.value }}
        </div>
    </template>
    <span v-else class="text-secondary">...</span>
</template>