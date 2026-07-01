<script setup lang="ts">

/**
 * Base Input to select tags
 * Uses the TagMenu as base for UI
 */

import TagMenu from './TagMenu.vue';
import TagBadge from '../tagtree/TagBadge.vue';
import { computed, ref, watch } from 'vue';
import { Property, Tag, PropertyType } from '@/data/models';



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
const emits = defineEmits(['update:modelValue', 'select', 'remove'])
defineExpose({
    focus
})

const tagMenuElem = ref(null)

// Private, owned copy of the selection — the rendered value comes from here, never straight
// from `props.modelValue`. The parents that host this component (TagPropInputDropdown,
// TagChildSelectDropdown) keep their OWN array and refill it in place (`arr.length = 0;
// arr.push(...)`) every time the underlying store value re-emits. That re-emit fires on any
// async boundary — notably while `data.addTag` is awaited during tag creation, whose commit
// runs `triggerRefs()`. If `localValue` shared the parent's array instance, that in-place
// refill would silently drop the tag we just added and snap the selection back to its
// pre-edit state. So we copy at every boundary and never hold an array we don't own.
// `skipNextSync` additionally swallows the echo of our own emit so it doesn't round-trip
// back in; genuine external updates still sync normally.
const localValue = ref<number[]>([...(props.modelValue ?? [])])
let skipNextSync = false

watch(() => props.modelValue, (val) => {
    if (skipNextSync) { skipNextSync = false; return }
    localValue.value = val ? [...val] : []
})

const tags = computed(() => localValue.value.map(id => props.property.tags[id]).filter(Boolean))
const allExcluded = computed(() => props.excluded ? [...props.excluded, ...localValue.value] : [...localValue.value])

function emitValue(newValue: number[]) {
    // Hand the parent its own array and keep a separate copy locally, so their in-place
    // refill of the emitted array can never mutate our buffer.
    localValue.value = [...newValue]
    skipNextSync = true
    emits('update:modelValue', newValue.length > 0 ? newValue : undefined)
}

function onSelect(tag: Tag) {
    if (props.property.type == PropertyType.tag && !props.forceMulti) {
        emitValue([tag.id])
    } else {
        emitValue([...localValue.value, tag.id])
    }

    emits('select', tag)
    focus()
}

function onCreate(tag: Tag) {
    onSelect(tag)
}

function onDelete(tagId: number) {
    emitValue(localValue.value.filter(i => i != tagId))
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
            <TagBadge @delete="removeTag(tag)" :show-delete="true" :id="tag.id" v-for="tag in tags" class="me-1" />
        </div>
        <TagMenu :property="props.property" :excluded="allExcluded" :can-create="props.canCreate"
            :can-customize="props.canCustomize" :can-link="props.canLink" :can-delete="props.canDelete"
            :auto-focus="props.autoFocus" @select="onSelect" @create="onCreate" @delete="onDelete" ref="tagMenuElem" />

    </div>
</template>