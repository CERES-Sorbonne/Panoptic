<script setup lang="ts">
import { Colors, Property, PropertyType } from '@/data/models';
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

const realValue = computed(() => {
    if([PropertyType._ahash, PropertyType._folders, PropertyType._sha1, PropertyType.string].indexOf(props.property.type) !== -1){
        return'"'+ props.value + '"'
    }
    else{
        return props.value
    }
})
</script>

<template>
    <template v-if="value != undefined">
        <div v-if="props.property.type == PropertyType._ahash">
            {{ realValue }}
        </div>
        <div v-if="props.property.type == PropertyType._folders">
            {{ realValue }}
        </div>
        <div v-if="props.property.type == PropertyType._sha1">
            {{ realValue }}
        </div>
        <div v-if="props.property.type == PropertyType.checkbox">
            <i v-if="realValue"  class="bi bi-square"></i>
            <i v-else class="bi bi-check-square"></i>
        </div>
        <div v-if="props.property.type == PropertyType.color" :style="{backgroundColor: color}" class="w-100 h-100">
        </div>
        <div v-if="props.property.type == PropertyType.date">
            {{ realValue }}
        </div>
        <div v-if="props.property.type == PropertyType.image_link">
        </div>
        <div v-if="props.property.type == PropertyType.multi_tags">
            <TagPreview :property-id="props.property.id" :value="realValue" />
        </div>
        <div v-if="props.property.type == PropertyType.number">
            {{ realValue }}
        </div>
        <div v-if="props.property.type == PropertyType.path">
            {{ realValue }}
        </div>
        <div v-if="props.property.type == PropertyType.string">
            {{ realValue }}
        </div>
        <div v-if="props.property.type == PropertyType.tag">
            <TagPreview :property-id="props.property.id" :value="realValue" />
        </div>
        <div v-if="props.property.type == PropertyType.url">
            {{ realValue }}
        </div>
    </template>
    <span v-else class="text-secondary">...</span>
</template>