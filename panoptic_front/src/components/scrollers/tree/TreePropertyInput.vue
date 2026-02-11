<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import PropertyIcon from '@/components/properties/PropertyIcon.vue';
import { Property, PropertyType, Instance } from '@/data/models';
import { deletedID, useDataStore } from '@/data/dataStore';
import { isTag } from '@/utils/utils';
import TagBadge from '@/components/tagtree/TagBadge.vue';
import DBInput from '@/components/property_inputs/DBInput.vue';
import CellTagInput from '@/components/property_cell_input/CellTagInput.vue';
import CellColorInput from '@/components/property_cell_input/CellColorInput.vue';
import RowTextInput from '@/components/property_row_input/RowTextInput.vue';
import CheckboxInput from '@/components/property_inputs/CheckboxInput.vue';
import RowDateInput from '@/components/property_row_input/RowDateInput.vue';
import RowUrlInput from '@/components/property_row_input/RowUrlInput.vue';
import RowNumberInput from '@/components/property_row_input/RowNumberInput.vue';
import { InputKey, useInputStore } from '@/data/inputStore';
import WithToolTip from '@/components/tooltips/withToolTip.vue';

const data = useDataStore()
const inputs = useInputStore()

const props = defineProps<{
    instance: Instance,
    groupId: number,
    property: Property
    width: number,
    idx: number,
    inputKey: string
}>()

const emits = defineEmits(['resize', 'update:selected'])

const focusElem = ref(null)
const key = computed(() => props.inputKey + '.' + props.property.id)
const width = computed(() => (props.width ?? 100) - 22)

const inputKey = computed(() => {
    const key = props.inputKey + '.' + props.property.id
    const idx = props.idx
    const instanceId = props.instance.id
    return { key, idx, instanceId: instanceId, groupId: props.groupId } as InputKey
})

function log() {
    console.log(focusElem.value)
    focusElem.value.focus()
}

function onFocus() {
    inputs.confirmOpen(key.value, props.idx, props.groupId, props.instance.id)
}

function onHide() {

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
            let val = inputs.requestInput
            if (!val) return
            if (val.instanceId == props.instance.id && val.key == key.value && val.groupId == props.groupId) {
                focusElem.value.focus()
            }
        })
    })
})

watch(() => inputs.requestInput, async (val) => {
    await nextTick()
    if (!val) return
    if (val.instanceId == props.instance.id && val.key == key.value && props.groupId == val.groupId) {
        focusElem.value.focus()
    }
})



</script>

<template>
    <DBInput v-if="props.instance.id != deletedID" :instance="props.instance" :property-id="props.property.id">
        <template #default="{ value, set }">
            <div class="d-flex text-nowrap overflow-hidden" style="height: 26px; line-height: 26px;font-size: 14px;">
                <WithToolTip :message="props.property.name">
                    <PropertyIcon v-if="props.property.type != PropertyType.checkbox && property.id > 0"
                        :type="property.type" style="margin-right: 2px;" @click="log" />
                </WithToolTip>

                <CellTagInput v-if="isTag(property.type)" :model-value="value" @update:model-value="set" :no-wrap="true"
                    :auto-focus="true" :can-create="true" :can-customize="true" :property="props.property"
                    :teleport="true" :width="width" ref="focusElem" @show="onFocus" @tab="inputs.requestInputNav()"
                    @hide="onHide" />

                <CellColorInput v-else-if="props.property.type == PropertyType.color" :model-value="value"
                    @update:model-value="set" :width="width" :rounded="true" :min-height="20" :teleport="true"
                    :offset="4" ref="focusElem" @focus="onFocus" @hide="onHide" />

                <RowNumberInput v-else-if="props.property.type == PropertyType.number" :model-value="value"
                    @update:model-value="set" :width="width" :height="26" :input-offset="3" ref="focusElem"
                    @focus="onFocus" @tab="inputs.requestInputNav()" @hide="onHide" />

                <RowTextInput v-else-if="props.property.type == PropertyType.string" :model-value="value"
                    @update:model-value="set" :width="width" :teleport="true" style="height: 25px;" ref="focusElem"
                    @focus="onFocus" @tab="inputs.requestInputNav()" @hide="onHide" />

                <RowUrlInput v-else-if="props.property.type == PropertyType.url" :model-value="value"
                    @update:model-value="set" :width="width" :teleport="true" ref="focusElem" @focus="onFocus"
                    @tab="inputs.requestInputNav()" @hide="onHide" />

                <CheckboxInput v-else-if="props.property.type == PropertyType.checkbox" :model-value="value"
                    @update:model-value="set" :label="props.property.name" :width="width" ref="focusElem"
                    @focus="onFocus" @tab="inputs.requestInputNav()" @hide="onHide" />

                <RowDateInput v-else-if="props.property.type == PropertyType.date" :model-value="value" :teleport="true"
                    @update:model-value="set" :width="width" ref="focusElem" @focus="onFocus"
                    @tab="inputs.requestInputNav()" @hide="onHide" />


                <div v-else class="d-flex flex-row overflow-hidden text-nowrap">
                    <PropertyIcon :type="property.type" style="margin-right: 3px;" />
                    <span v-if="property.type == PropertyType._folders">
                        <TagBadge
                            :name="data.folders[data.instances[props.instance.id].properties[props.property.id]].name"
                            :color="-1" />
                    </span>
                    <span v-else>{{ data.instances[props.instance.id].properties[props.property.id] }}</span>
                </div>
            </div>
        </template>
    </DBInput>
</template>

<style scoped></style>