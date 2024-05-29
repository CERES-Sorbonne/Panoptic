<script setup lang="ts">

/**
 * Base Input to select tags
 * Uses the TagMenu as base for UI
 */

import TagMenu from './TagMenu.vue';
import TagBadge from '../tagtree/TagBadge.vue';
import { computed, ref } from 'vue';
import { Property, Tag, PropertyType } from '@/data/models';



const props = defineProps({
    property: Object as () => Property,
    modelValue: Array<number>,
    excluded: Array<number>,
    canCreate: Boolean,
    canCustomize: Boolean,
    canLink: Boolean,
    canDelete: Boolean,
    autoFocus: Boolean
})
const emits = defineEmits(['update:modelValue', 'select', 'remove'])
defineExpose({
    focus
})

const tagMenuElem = ref(null)

const safeValue = computed(() => props.modelValue ?? [])
const tags = computed(() => safeValue.value.map(id => props.property.tags[id]))
const allExcluded = computed(() => props.excluded ? [...props.excluded, ...safeValue.value] : [...safeValue.value])

function onSelect(tag: Tag) {
    if(props.property.type == PropertyType.tag) {
        emits('update:modelValue', [tag.id])
    } else {
        emits('update:modelValue', [...safeValue.value, tag.id])
    }

    emits('select', tag)
    focus()
}

function onCreate(tag: Tag) {
    onSelect(tag)
}

function onDelete(tagId: number) {
    emits('update:modelValue', [...safeValue.value.filter(i => i != tagId)])
    emits('remove', tagId)
    focus()
}

function removeTag(tag: Tag) {
    onDelete(tag.id)
}

function focus() {
    tagMenuElem.value.focus()
}

</script>

<template>
    <div>
        <div class="overflow-hidden mb-1 text-wrap">
            <TagBadge @delete="removeTag(tag)" :show-delete="true" :tag="tag.value" :color="tag.color"
                            v-for="tag in tags" class="me-1"/>
        </div>
        <TagMenu :property="props.property" :excluded="allExcluded" :can-create="props.canCreate"
            :can-customize="props.canCustomize" :can-link="props.canLink" :can-delete="props.canDelete" :auto-focus="props.autoFocus" @select="onSelect" @create="onCreate" @delete="onDelete" ref="tagMenuElem"/>

    </div>
</template>