<script setup lang="ts">

/**
 * Input to select tags as a Dropdown
 * Uses the TagInput inside the dropdown popup
 */

import { Property } from '@/data/models';
import Dropdown from '../dropdowns/Dropdown.vue';
import TagInput from './TagInput.vue';
import { computed, nextTick, ref } from 'vue';
import { globalStore } from '@/data/store';
import TagBadge from '../tagtree/TagBadge.vue';


const props = defineProps({
    property: Object as () => Property,
    modelValue: Array<number>,
    excluded: Array<number>,
    canCreate: Boolean,
    canCustomize: Boolean,
    canLink: Boolean,
    canDelete: Boolean,
    autoFocus: Boolean,
    noWrap: Boolean
})
const emits = defineEmits(['update:modelValue', 'hide'])
defineExpose({
    getHeight
})
const heightElem = ref(null)
const inputElem = ref(null)

const safeValue = computed(() => props.modelValue ?? [])
const tags = computed(() => safeValue.value.map(tId => globalStore.tags[props.property.id][tId]))

function getHeight() {
    if(heightElem.value == undefined) return 0
    return heightElem.value.clientHeight
}

function test() {
    inputElem.value.focus()
}

</script>

<template>
    <Dropdown :auto-focus="false" @hide="emits('hide')">
        <template #button>
            <div class="btn-class" :class="props.noWrap ? 'text-nowrap' : 'text-wrap'" ref="heightElem">
                <span v-for="tag in tags">
                    <TagBadge :tag="tag.value" :color="tag.color" class="me-1" />
                </span>
                <span v-if="tags.length == 0" class="text-secondary">None</span>
            </div>
        </template>

        <template #popup>
            <div class="p-1" style="max-width: 250px;">
                <TagInput :property="props.property" :model-value="safeValue" :excluded="props.excluded"
                    :can-create="props.canCreate" :can-customize="props.canCustomize" :can-link="props.canLink"
                    :can-delete="props.canDelete" :auto-focus="props.autoFocus"
                    @update:model-value="v => emits('update:modelValue', v)" ref="inputElem"/>
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