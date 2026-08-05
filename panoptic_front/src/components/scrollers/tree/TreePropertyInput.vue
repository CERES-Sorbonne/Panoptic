<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, provide, ref, watch } from 'vue'
import { hoverPropertyKey } from '@/data/hoverStore'
import { deletedID, isReadonly, Property, PropertyType, Instance } from '@/data/models';
import { isTag } from '@/utils/utils';
import DBInput from '@/components/property_inputs/DBInput.vue';
import TreeTextInput from './TreeTextInput.vue';
import TreeNumberInput from './TreeNumberInput.vue';
import TreeCheckboxInput from './TreeCheckboxInput.vue';
import TreeTagInput from './TreeTagInput.vue';
import TreeColorInput from './TreeColorInput.vue';
import TreeDateInput from './TreeDateInput.vue';
import TreeValueRow from './TreeValueRow.vue';
import { InputKey, useInputStore } from '@/data/inputStore';

const inputs = useInputStore()

const props = defineProps<{
    instance: Instance,
    groupId: number,
    property: Property
    idx: number,
    inputKey: string
}>()

// so the frame below can report hover/focus on this property to the hover store
provide(hoverPropertyKey, () => props.property.id)

const focusElem = ref(null)
const key = computed(() => props.inputKey + '.' + props.property.id)

const inputKey = computed(() => ({
    key: key.value,
    idx: props.idx,
    instanceId: props.instance.id,
    groupId: props.groupId
} as InputKey))

function onFocus() {
    inputs.confirmOpen(key.value, props.idx, props.groupId, props.instance.id)
}

function focusRequested(val: InputKey) {
    return val && val.instanceId == props.instance.id && val.key == key.value && val.groupId == props.groupId
}

onMounted(() => inputs.addInput(key.value, props.idx, props.groupId, props.instance.id))
onUnmounted(() => inputs.removeInput(key.value, props.idx))

watch(inputKey, (newVal, oldVal) => {
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
                    @focus="onFocus" @tab="inputs.requestInputNav()" />

                <TreeNumberInput v-else-if="props.property.type == PropertyType.number" :model-value="value"
                    @update:model-value="set" ref="focusElem" @focus="onFocus" @tab="inputs.requestInputNav()" />

                <TreeCheckboxInput v-else-if="props.property.type == PropertyType.checkbox" :model-value="value"
                    :label="props.property.name" @update:model-value="set" ref="focusElem" @focus="onFocus"
                    @tab="inputs.requestInputNav()" />

                <TreeTagInput v-else-if="isTag(props.property.type)" :model-value="value" :property="props.property"
                    :instance-id="props.instance.id" @update:model-value="set" ref="focusElem" @focus="onFocus"
                    @tab="inputs.requestInputNav()" />

                <TreeColorInput v-else-if="props.property.type == PropertyType.color" :model-value="value"
                    @update:model-value="set" ref="focusElem" @focus="onFocus" @tab="inputs.requestInputNav()" />

                <TreeDateInput v-else-if="props.property.type == PropertyType.date" :model-value="value"
                    @update:model-value="set" ref="focusElem" @focus="onFocus" @tab="inputs.requestInputNav()" />

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
