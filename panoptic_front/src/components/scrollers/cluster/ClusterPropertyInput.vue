<script setup lang="ts">
// A single-row, typed property editor for one cluster card, rendered BELOW the image
// (not overlaid). It mirrors the typed inputs of TreePropertyInput, but instead of binding
// to one instance's DB value it shows the cluster's shared value and emits the new value up —
// ClusterView applies it to every instance in the cluster.
import { computed } from 'vue'
import PropertyIcon from '@/components/properties/PropertyIcon.vue'
import TagBadge from '@/components/tagtree/TagBadge.vue'
import CellTagInput from '@/components/property_cell_input/CellTagInput.vue'
import CellColorInput from '@/components/property_cell_input/CellColorInput.vue'
import RowTextInput from '@/components/property_row_input/RowTextInput.vue'
import RowNumberInput from '@/components/property_row_input/RowNumberInput.vue'
import RowUrlInput from '@/components/property_row_input/RowUrlInput.vue'
import RowDateInput from '@/components/property_row_input/RowDateInput.vue'
import CheckboxInput from '@/components/property_inputs/CheckboxInput.vue'
import { Property, PropertyType } from '@/data/models'
import { isTag } from '@/utils/utils'

const props = defineProps<{
    property: Property
    // The cluster's shared value on this property (undefined when the pile is undecided).
    modelValue?: any
    // Representative instance of the cluster, passed to the tag input as creation context.
    instanceId?: number
    width: number
    // Caps how wide the edit popup may grow — for the inspector header, where the input owns
    // a fixed half of the row and must not spill over the group name.
    maxWidth?: number
}>()

const emits = defineEmits(['update:modelValue'])

// Leave room for the property icon (like TreePropertyInput does with -22).
const innerWidth = computed(() => Math.max(20, (props.width ?? 100) - 22))

function set(v: any) {
    emits('update:modelValue', v)
}
</script>

<template>
    <div class="cluster-prop-input d-flex text-nowrap overflow-hidden" @click.stop>
        <PropertyIcon v-if="property.type != PropertyType.checkbox && property.id > 0"
            :type="property.type" class="cpi-icon" />

        <!-- forceMono: at group level a multi-tag property acts like a mono-tag — one tag per group. -->
        <CellTagInput v-if="isTag(property.type)" :model-value="modelValue" :instance-id="props.instanceId"
            @update:model-value="set" :no-wrap="true" :can-create="true" :can-customize="true"
            :force-mono="true" :property="props.property" :teleport="true" :width="innerWidth" />

        <CellColorInput v-else-if="property.type == PropertyType.color" :model-value="modelValue"
            @update:model-value="set" :width="innerWidth" :rounded="true" :min-height="20" :teleport="true"
            :offset="4" />

        <RowNumberInput v-else-if="property.type == PropertyType.number" :model-value="modelValue"
            @update:model-value="set" :width="innerWidth" :height="24" :input-offset="3" />

        <RowTextInput v-else-if="property.type == PropertyType.string" :model-value="modelValue"
            @update:model-value="set" :width="innerWidth" :max-width="props.maxWidth" :teleport="true" />

        <RowUrlInput v-else-if="property.type == PropertyType.url" :model-value="modelValue"
            @update:model-value="set" :width="innerWidth" :teleport="true" />

        <CheckboxInput v-else-if="property.type == PropertyType.checkbox" :model-value="modelValue"
            @update:model-value="set" :label="props.property.name" :width="innerWidth" />

        <RowDateInput v-else-if="property.type == PropertyType.date" :model-value="modelValue" :teleport="true"
            @update:model-value="set" :width="innerWidth" />

        <span v-else class="cpi-fallback">{{ modelValue }}</span>
    </div>
</template>

<style scoped>
.cluster-prop-input {
    height: 26px;
    line-height: 26px;
    font-size: 13px;
    align-items: center;
    color: var(--text-primary);
}

.cpi-icon {
    margin-right: 3px;
    flex-shrink: 0;
}

.cpi-fallback {
    overflow: hidden;
    text-overflow: ellipsis;
}
</style>
