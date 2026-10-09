<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, onUnmounted, provide, ref, watch } from 'vue'
import { hoverPropertyKey } from '@/data/stores/hoverStore'
import { deletedID, isReadonly, Property, PropertyType } from '@/data/models';
import { InstanceEntry } from '@/data/stores/instanceStore';
import { isTag } from '@/utils/utils';
import DBInput from '@/components/property_inputs/DBInput.vue';
import TreeTextInput from './TreeTextInput.vue';
import TreeNumberInput from './TreeNumberInput.vue';
import TreeCheckboxInput from './TreeCheckboxInput.vue';
import TreeTagInput from './TreeTagInput.vue';
import TreeColorInput from './TreeColorInput.vue';
import TreeDateInput from './TreeDateInput.vue';
import TreeValueRow from './TreeValueRow.vue';
import { InputKey, useInputStore } from '@/data/stores/inputStore';
import { keyState } from '@/data/composables/keyState';
import { cellValueKey } from './cellValue';
import { CellKey } from '../cellEditing';

const inputs = useInputStore()

const props = defineProps<{
    instance: InstanceEntry,
    groupId: number,
    property: Property
    // Image order and scroller key, for Tab navigation through inputStore (ImageScroller). Unused
    // in editor mode.
    idx?: number,
    inputKey?: string
    // Editor mode (the tree scroller, which draws its rows with TreeCellView and mounts this only
    // for the row being edited): opens the editor on mount, reports `close` once it is done and
    // `tab` instead of going through inputStore.
    open?: boolean
}>()

const emits = defineEmits<{
    close: [cell: CellKey]
    tab: [cell: CellKey, backwards: boolean]
}>()

// so the frame below can report hover/focus on this property to the hover store
provide(hoverPropertyKey, () => props.property.id)
// and so it can filter the tab on this row's value
provide(cellValueKey, () => ({ propertyId: props.property.id, value: props.instance.properties[props.property.id] }))

const focusElem = ref(null)
const key = computed(() => props.inputKey + '.' + props.property.id)

const inputKey = computed(() => ({
    key: key.value,
    idx: props.idx,
    instanceId: props.instance.id,
    groupId: props.groupId
} as InputKey))

const cell = (): CellKey => ({ instanceId: props.instance.id, groupId: props.groupId, propertyId: props.property.id })

function onFocus() {
    if (props.open) return
    inputs.confirmOpen(key.value, props.idx, props.groupId, props.instance.id)
}

function onTab() {
    if (props.open) emits('tab', cell(), keyState.shift)
    else inputs.requestInputNav()
}

// Every typed input reports `blur` once its edit is over, committed or cancelled — the textarea or
// number field losing focus, the tag picker or a dropdown closing. Closing an already closed cell
// is a no-op, so a second report (see onBeforeUnmount) costs nothing.
function onBlur() {
    if (props.open) emits('close', cell())
}

function focusRequested(val: InputKey) {
    return val && val.instanceId == props.instance.id && val.key == key.value && val.groupId == props.groupId
}

onMounted(async () => {
    if (props.open) {
        // the typed input is mounted with this component, but some only measure their cell
        // (the popups) once it is laid out
        await nextTick()
        focusElem.value?.focus()
        return
    }
    inputs.addInput(key.value, props.idx, props.groupId, props.instance.id)
})
onUnmounted(() => {
    if (!props.open) inputs.removeInput(key.value, props.idx)
})
// Unmounted by its card before it closed (the card was recycled to another image, the group
// closed): the cell must not stay open, or its editor would pop up again whenever that image is
// next drawn.
onBeforeUnmount(onBlur)

watch(inputKey, (newVal, oldVal) => {
    if (props.open) return
    if (newVal.groupId == oldVal.groupId &&
        newVal.idx == oldVal.idx &&
        newVal.key == oldVal.key &&
        newVal.instanceId == oldVal.instanceId) {
        return
    }

    inputs.removeInput(oldVal.key, oldVal.idx)
    nextTick(() => {
        inputs.addInput(newVal.key, newVal.idx, newVal.groupId, newVal.instanceId)
        nextTick(() => {
            if (focusRequested(inputs.requestInput)) focusElem.value?.focus()
        })
    })
})

watch(() => inputs.requestInput, async (val) => {
    if (props.open) return
    await nextTick()
    if (focusRequested(val)) focusElem.value?.focus()
})

</script>

<template>
    <!-- Computed / non-editable properties: value only, no input. -->
    <TreeValueRow v-if="isReadonly(props.property)" :property="props.property"
        :value="props.instance.properties[props.property.id]" />

    <DBInput v-else-if="props.instance.id != deletedID" :instance="props.instance" :property-id="props.property.id">
        <template #default="{ value, set, status }">
            <div :class="{ 'value-unconfirmed': status !== 'confirmed' }"
                :title="status === 'pending' ? 'Saving…' : (status === 'error' ? 'Failed to save' : undefined)">

                <!-- Inputs built for this scroller: they fill the cell and draw their own frame,
                     property icon included, so nothing here sizes or decorates them. -->
                <TreeTextInput
                    v-if="props.property.type == PropertyType.string || props.property.type == PropertyType.url"
                    :model-value="value" :type="props.property.type" @update:model-value="set" ref="focusElem"
                    @focus="onFocus" @tab="onTab" @blur="onBlur" />

                <TreeNumberInput v-else-if="props.property.type == PropertyType.number" :model-value="value"
                    @update:model-value="set" ref="focusElem" @focus="onFocus" @tab="onTab" @blur="onBlur" />

                <TreeCheckboxInput v-else-if="props.property.type == PropertyType.checkbox" :model-value="value"
                    :label="props.property.name" @update:model-value="set" ref="focusElem" @focus="onFocus"
                    @tab="onTab" @blur="onBlur" />

                <TreeTagInput v-else-if="isTag(props.property.type)" :model-value="value" :property="props.property"
                    :instance-id="props.instance.id" @update:model-value="set" ref="focusElem" @focus="onFocus"
                    @tab="onTab" @blur="onBlur" />

                <TreeColorInput v-else-if="props.property.type == PropertyType.color" :model-value="value"
                    @update:model-value="set" ref="focusElem" @focus="onFocus" @tab="onTab" @blur="onBlur" />

                <TreeDateInput v-else-if="props.property.type == PropertyType.date" :model-value="value"
                    @update:model-value="set" ref="focusElem" @focus="onFocus" @tab="onTab" @blur="onBlur" />

                <!-- any type without a dedicated input yet: value only -->
                <TreeValueRow v-else :property="props.property" :value="value" />
            </div>
        </template>
    </DBInput>
</template>

<style scoped>
.value-unconfirmed {
    opacity: 0.45;
    background-color: var(--light-grey);
    transition: opacity 0.15s ease, background-color 0.15s ease;
}

/* the pixel-sized editors have no frame of their own, so the row height lives here */
.legacy-row {
    height: 26px;
    line-height: 26px;
    font-size: 14px;
}
</style>
