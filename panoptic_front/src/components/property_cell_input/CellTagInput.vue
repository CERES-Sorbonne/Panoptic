<script setup lang="ts">

/**
 * Input to select tags as a Dropdown
 * Uses the TagInput inside the dropdown popup
 */

import Dropdown from '@/components/dropdowns/Dropdown.vue';
import TagInput from '@/components/property_inputs/TagInput.vue';
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import TagBadge from '@/components/tagtree/TagBadge.vue';
import { Property, PropertyType } from '@/data/models';
import { useDataStore } from '@/data/dataStore';

const data = useDataStore()

const props = defineProps<{
    property: Property
    modelValue?: number[]
    excluded?: number[]
    canCreate?: boolean
    canCustomize?: boolean
    canLink?: boolean
    canDelete?: boolean
    autoFocus?: boolean
    noWrap?: boolean
    teleport?: boolean
    minHeight?: number
    width?: number
    forceMulti?: boolean
    instanceId?: number
}>()
const emits = defineEmits(['update:modelValue', 'hide', 'update:height', 'show', 'tab'])
defineExpose({
    getHeight,
    focus
})
const heightElem = ref(null)
const inputElem = ref(null)
const dropdownElem = ref(null)
const safeValue = computed(() => localValue.value ?? [])
const tags = computed(() => safeValue.value.map(id => data.tags[id]))

const localValue = ref(undefined)
// True while the dropdown popup is open, i.e. the user is mid-edit.
const isOpen = ref(false)

function getHeight() {
    if (heightElem.value == undefined) return 0
    return heightElem.value.clientHeight
}

async function updateValue(value, hide) {
    localValue.value = value
    updateHeight()
    if(props.property.type == PropertyType.tag && !props.forceMulti) {
        hide()
    }
}

async function updateHeight() {
    await nextTick()
    emits('update:height', getHeight())
}

function focus() {
    if (!dropdownElem.value) return
    dropdownElem.value.show()
}

function updateLocal() {
    // While the dropdown is open, `localValue` is the user's working selection and the
    // single source of truth — never overwrite it from `props.modelValue`. In the tree,
    // creating a tag runs `data.addTag` -> commit -> `triggerRefs()`, which re-renders the
    // virtual scroller and hands us a fresh instance object. That makes `props.modelValue`
    // change identity (same pre-edit value, new array) mid-edit, and a blind sync here would
    // snap the selection back to its pre-edit state, dropping the tag just added. Closed, we
    // sync normally so the cell reflects the confirmed value.
    if (isOpen.value) return
    localValue.value = props.modelValue
}

function onHide() {
    isOpen.value = false
    emits('hide')
    emits('update:modelValue', localValue.value)
}

function onShow() {
    // Snapshot the current committed value as the editing baseline, then stop syncing.
    localValue.value = props.modelValue
    isOpen.value = true
    emits('show')
}

function onTab(hide) {
    emits('tab')
    hide()
}

watch(() => props.width, updateHeight)
watch(() => props.modelValue, updateLocal)
onMounted(updateHeight)
onMounted(updateLocal)

</script>

<template>
    <Dropdown :auto-focus="false" @show="onShow" @hide="onHide" :teleport="props.teleport" ref="dropdownElem" :offset="-25" placement="bottom-start">
        <template #button>
            <div class="btn-class" :class="props.noWrap ? 'text-nowrap' : 'text-wrap'"
                :style="{ width: props.width ? props.width + 'px' : '100%' }" ref="heightElem">
                <span v-for="tag in tags">
                    <TagBadge v-if="tag" :id="tag.id" class="me-1" />
                </span>
                <span v-if="tags.length == 0" style="font-size: 14px;" class="text-secondary">{{ $t('none') }}</span>
            </div>
        </template>

        <template #popup="{hide}">
            <div class="p-1" style="max-width: 250px;">
                <TagInput :property="props.property" :model-value="safeValue" :excluded="props.excluded"
                    :can-create="props.canCreate" :can-customize="props.canCustomize" :can-link="props.canLink"
                    :can-delete="props.canDelete" :auto-focus="props.autoFocus" @update:model-value="v => updateValue(v, hide)"
                    :force-multi="props.forceMulti" :instance-id="props.instanceId" @tab="onTab(hide)"
                    ref="inputElem" />
            </div>
        </template>
    </Dropdown>
</template>

<style scoped>
.btn-class {
    overflow: hidden;
    cursor: pointer;
}
</style>