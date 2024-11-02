<script setup lang="ts">

/**
 * Input to select tags as a Dropdown
 * Uses the TagInput inside the dropdown popup
 */

import Dropdown from '@/components/dropdowns/Dropdown.vue';
import TagInput from '@/components/property_inputs/TagInput.vue';
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import TagBadge from '@/components/tagtree/TagBadge.vue';
import { Property } from '@/data/models';

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
}>()
const emits = defineEmits(['update:modelValue', 'hide', 'update:height'])
defineExpose({
    getHeight,
    focus
})
const heightElem = ref(null)
const inputElem = ref(null)
const dropdownElem = ref(null)
const safeValue = computed(() => props.modelValue ?? [])
const tags = computed(() => safeValue.value.map(tId => props.property.tags[tId]))

function getHeight() {
    if (heightElem.value == undefined) return 0
    return heightElem.value.clientHeight
}

async function updateValue(value) {
    emits('update:modelValue', value)
    updateHeight()
}

async function updateHeight() {
    await nextTick()
    emits('update:height', getHeight())
}

function focus() {
    if (!dropdownElem.value) return
    dropdownElem.value.show()
}

watch(() => props.width, updateHeight)
onMounted(updateHeight)
</script>

<template>
    <Dropdown :auto-focus="false" @hide="emits('hide')" :teleport="props.teleport" ref="dropdownElem">
        <template #button>
            <div class="btn-class bb" :class="props.noWrap ? 'text-nowrap' : 'text-wrap'"
                :style="{ width: props.width ? props.width + 'px' : '100%' }" ref="heightElem">
                <span v-for="tag in tags">
                    <TagBadge :id="tag.id" class="me-1" />
                </span>
                <span v-if="tags.length == 0" class="text-secondary">None</span>
            </div>
        </template>

        <template #popup>
            <div class="p-1" style="max-width: 250px;">
                <TagInput :property="props.property" :model-value="safeValue" :excluded="props.excluded"
                    :can-create="props.canCreate" :can-customize="props.canCustomize" :can-link="props.canLink"
                    :can-delete="props.canDelete" :auto-focus="props.autoFocus" @update:model-value="updateValue"
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