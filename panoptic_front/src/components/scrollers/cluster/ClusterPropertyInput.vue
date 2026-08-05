<script setup lang="ts">
// A single-row, typed property editor for one cluster card (and for the inspector header).
// It renders the SAME inputs as the tree scroller (Tree*Input + TreeCellFrame): they fill their
// container instead of being sized in pixels, and draw their own frame and property icon.
// The only difference with TreePropertyInput is the binding: instead of one instance's DB value
// it shows the cluster's shared value and emits the new value up — GroupView applies it to every
// instance in the cluster.
import TreeTextInput from '@/components/scrollers/tree/TreeTextInput.vue'
import TreeNumberInput from '@/components/scrollers/tree/TreeNumberInput.vue'
import TreeCheckboxInput from '@/components/scrollers/tree/TreeCheckboxInput.vue'
import TreeTagInput from '@/components/scrollers/tree/TreeTagInput.vue'
import TreeColorInput from '@/components/scrollers/tree/TreeColorInput.vue'
import TreeDateInput from '@/components/scrollers/tree/TreeDateInput.vue'
import TreeValueRow from '@/components/scrollers/tree/TreeValueRow.vue'
import { Property, PropertyType, isReadonly } from '@/data/models'
import { isTag } from '@/utils/utils'
import { provide } from 'vue'
import { hoverPropertyKey } from '@/data/hoverStore'

const props = defineProps<{
    property: Property
    // The cluster's shared value on this property (undefined when the pile is undecided).
    modelValue?: any
    // Representative instance of the cluster, passed to the tag input as creation context.
    instanceId?: number
    // Kept for the callers' layout; the inputs themselves fill 100% of this box.
    width?: number
    maxWidth?: number
}>()

const emits = defineEmits(['update:modelValue'])

// so the frame below can report hover/focus on this property to the hover store
provide(hoverPropertyKey, () => props.property.id)

// Same value in, same value out — don't assign. The inputs are edit-in-place cells: closing
// one always reports its value, whether or not the user changed anything (the tag popup, for
// instance, emits its selection on hide). Re-assigning an unchanged value is not free here —
// it rewrites the property on the whole pile and drains it — so a plain focus/blur would look
// like it wiped the card. Only a real change is an assignment.
function sameValue(a: any, b: any) {
    if (a === b) return true
    if (a == null && b == null) return true
    if (Array.isArray(a) && Array.isArray(b)) {
        return a.length === b.length && a.every((v, i) => v === b[i])
    }
    return false
}

function set(v: any) {
    if (sameValue(v, props.modelValue)) return
    emits('update:modelValue', v)
}
</script>

<template>
    <div class="cluster-prop-input" :style="{ width: props.width ? props.width + 'px' : '100%' }" @click.stop>
        <!-- Computed / non-editable properties: value only, no input. -->
        <TreeValueRow v-if="isReadonly(props.property)" :property="props.property" :value="props.modelValue" />

        <TreeTextInput v-else-if="property.type == PropertyType.string || property.type == PropertyType.url"
            :model-value="modelValue" :type="props.property.type" @update:model-value="set" />

        <TreeNumberInput v-else-if="property.type == PropertyType.number" :model-value="modelValue"
            @update:model-value="set" />

        <TreeCheckboxInput v-else-if="property.type == PropertyType.checkbox" :model-value="modelValue"
            :label="props.property.name" @update:model-value="set" />

        <!-- forceMono: at group level a multi-tag property acts like a mono-tag — one tag per group. -->
        <TreeTagInput v-else-if="isTag(property.type)" :model-value="modelValue" :property="props.property"
            :instance-id="props.instanceId" :force-mono="true" @update:model-value="set" />

        <TreeColorInput v-else-if="property.type == PropertyType.color" :model-value="modelValue"
            @update:model-value="set" />

        <TreeDateInput v-else-if="property.type == PropertyType.date" :model-value="modelValue"
            @update:model-value="set" />

        <TreeValueRow v-else :property="props.property" :value="props.modelValue" />
    </div>
</template>

<style scoped>
.cluster-prop-input {
    min-width: 0;
    overflow: hidden;
    color: var(--text-primary);
}
</style>
