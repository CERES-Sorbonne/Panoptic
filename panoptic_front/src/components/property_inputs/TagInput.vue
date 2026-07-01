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
import { useInstanceStore } from '@/data/instanceStore';

const data = useDataStore()
const instanceStore = useInstanceStore()

const props = defineProps<{
    property: Property,
    modelValue?: number[],
    excluded?: number[],
    canCreate?: boolean,
    canCustomize?: boolean,
    canLink?: boolean,
    canDelete?: boolean,
    autoFocus?: boolean,
    forceMulti?: boolean,
    instanceId?: number
}>()
const emits = defineEmits(['update:modelValue', 'select', 'remove', 'tab'])
defineExpose({
    focus
})

const tagMenuElem = ref(null)

const safeValue = computed(() => props.modelValue ?? [])
const tags = computed(() => safeValue.value.map(id => data.tags[id]))
const allExcluded = computed(() => props.excluded ? [...props.excluded, ...safeValue.value] : [...safeValue.value])

// When editing a concrete instance, union `safeValue` (this session's accumulated local
// edits) with the CURRENT value straight from instanceStore. `safeValue` alone can go
// stale across an async gap — e.g. while `data.addTag` is awaited to create a brand-new
// tag — silently dropping tags that were already assigned but hadn't reached this
// component's local snapshot yet. instanceStore.instanceData is the canonical live source,
// so unioning against it can only ever add missing tags back in, never drop one.
function currentValue(): number[] {
    if (props.instanceId == null) return safeValue.value
    const fromStore: number[] = instanceStore.instanceData[props.instanceId]?.properties[props.property.id] ?? []
    return [...new Set([...safeValue.value, ...fromStore])]
}

function onSelect(tag: Tag) {
    if (props.property.type == PropertyType.tag && !props.forceMulti) {
        emits('update:modelValue', [tag.id])
    } else {
        emits('update:modelValue', [...new Set([...currentValue(), tag.id])])
    }

    emits('select', tag)
    focus()
}

function onCreate(tag: Tag) {
    onSelect(tag)
}

function onDelete(tagId: number) {
    emits('update:modelValue', currentValue().filter(i => i != tagId))
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