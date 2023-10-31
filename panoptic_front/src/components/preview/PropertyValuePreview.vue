<script setup lang="ts">
import { Colors, Property, PropertyMode, PropertyType } from '@/data/models';
import TagPreview from './TagPreview.vue';
import { computed } from 'vue';

const props = defineProps({
    value: undefined,
    property: Object as () => Property
})

const color = computed(() => {
    if (props.value == undefined) return 'white'

    let value = Number(props.value)
    if (isNaN(value) || value > 12) return 'gray'
    return Colors[value].color
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
        <div v-if="props.property.type == PropertyType.color" :style="{backgroundColor: color}" class="w-100 h-100">
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