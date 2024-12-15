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
}>()
const emits = defineEmits(['update:modelValue', 'hide', 'update:height'])
defineExpose({
    getHeight,
    focus
})
const heightElem = ref(null)
const inputElem = ref(null)
const dropdownElem = ref(null)
const safeValue = computed(() => localValue.value ?? [])
const tags = computed(() => safeValue.value.map(tId => props.property.tags[tId]))

const localValue = ref(undefined)

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
    localValue.value = props.modelValue
}

function onHide() {
    emits('hide')
    emits('update:modelValue', localValue.value)
}

watch(() => props.width, updateHeight)
watch(() => props.modelValue, updateLocal)
onMounted(updateHeight)
onMounted(updateLocal)

</script>

<template>
    <Dropdown :auto-focus="false" @hide="onHide" :teleport="props.teleport" ref="dropdownElem" :offset="-25" placement="bottom-start">
        <template #button>
            <div class="btn-class" :class="props.noWrap ? 'text-nowrap' : 'text-wrap'"
                :style="{ width: props.width ? props.width + 'px' : '100%' }" ref="heightElem">
                <span v-for="tag in tags">
                    <TagBadge :id="tag.id" class="me-1" />
                </span>
                <span v-if="tags.length == 0" style="font-size: 14px;" class="text-secondary">{{ $t('none') }}</span>
            </div>
        </template>

        <template #popup="{hide}">
            <div class="p-1" style="max-width: 250px;">
                <TagInput :property="props.property" :model-value="safeValue" :excluded="props.excluded"
                    :can-create="props.canCreate" :can-customize="props.canCustomize" :can-link="props.canLink"
                    :can-delete="props.canDelete" :auto-focus="props.autoFocus" @update:model-value="v => updateValue(v, hide)"
                    :force-multi="true"
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