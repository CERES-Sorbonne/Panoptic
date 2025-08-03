<script setup lang="ts">

/**
 * Base Input to select tags
 * Uses the TagMenu as base for UI
 */

import TagMenu from '@/components/tags/TagMenu.vue';
import TagBadge from '@/components/tagtree/TagBadge.vue';
import { computed, ref } from 'vue';
import { Property, Tag, PropertyType } from '@/data/models';
import { useDataStore } from '@/data/dataStore';

const data = useDataStore()

const props = defineProps<{
    property: Property,
    modelValue?: number[],
    excluded?: number[],
    canCreate?: boolean,
    canCustomize?: boolean,
    canLink?: boolean,
    canDelete?: boolean,
    autoFocus?: boolean,
    forceMulti?: boolean
}>()
const emits = defineEmits(['update:modelValue', 'select', 'remove', 'tab'])
defineExpose({
    focus
})

const tagMenuElem = ref(null)

const safeValue = computed(() => props.modelValue ?? [])
const tags = computed(() => safeValue.value.map(id => data.tags[id]))
const allExcluded = computed(() => props.excluded ? [...props.excluded, ...safeValue.value] : [...safeValue.value])

function onSelect(tag: Tag) {
    if (props.property.type == PropertyType.tag && !props.forceMulti) {
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
            <template v-for="tag in tags">
                <TagBadge v-if="tag" @delete="removeTag(tag)" :show-delete="true" :id="tag.id" class="me-1" />
            </template>

        </div>
        <TagMenu :property="props.property" :excluded="allExcluded" :can-create="props.canCreate"
            :can-customize="props.canCustomize" :can-link="props.canLink" :can-delete="props.canDelete"
            :auto-focus="props.autoFocus" @select="onSelect" @create="onCreate" @delete="onDelete" ref="tagMenuElem"
            @tab="emits('tab')" />

    </div>
</template>