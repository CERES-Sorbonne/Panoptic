<script setup lang="ts">
import SelectCircle from '@/components/inputs/SelectCircle.vue';
import PropertyValueVue from '@/components/properties/PropertyValue.vue';
import { Group, GroupType, SelectedImages } from '@/core/GroupManager';
import { GroupLine } from '@/components/scrollers/types';
import { getGroupParents } from '@/utils/utils';
import { Ref, computed } from 'vue';
import { useColumnStore } from '@/data/stores/columnStore';



const props = defineProps<{
  item: GroupLine
  width: number
}>()

const emits = defineEmits(['close:group', 'open:group', 'toggle:group'])

const columnStore = useColumnStore()

const closed = computed(() => getGroupParents(props.item.data).some(g => g.view.closed) || props.item.data.view.closed)

function toggleClosed() {
    if (closed.value) {
        emits('open:group', props.item.data.id)
    }
    else {
        emits('close:group', props.item.data.id)
    }
}

const selected = computed(() => {
    columnStore.selectionVersion  // reactive dep on global selection (step 2)
    return !props.item.data.slots.some(s => !columnStore.isSelected(s))
})

// A cluster group has no property values, so it is labelled by its name instead.
type Label = { value?: Group['meta']['propertyValues'][number], name?: string }

const labels = computed(() => {
    const res: Label[] = []
    if (props.item.data.id != undefined) {
        for (const group of [props.item.data, ...getGroupParents(props.item.data)]) {
            if (group.meta.propertyValues.length) {
                group.meta.propertyValues.forEach(value => res.push({ value }))
            } else if (group.type == GroupType.Cluster) {
                res.push({ name: group.name ?? ('Cluster ' + group.parentIdx) })
            }
        }
    }
    return res
})

</script>

<template>
    <div class="d-flex flex-row group-row m-0"
        :style="{ width: (props.width - 0) + 'px', height: (props.item.size) + 'px' }">
        <div @click="toggleClosed" class="align-self-center" style="cursor: pointer; margin-left: 0.25rem;">
            <i v-if="closed" class="bi bi-caret-right-fill" style="margin-left: 1px;"></i>
            <i v-else class="bi bi-caret-down-fill" style="margin-left: 1px;"></i>
        </div>
        <div class="ms-1 me-2"><SelectCircle :model-value="selected" @update:model-value="emits('toggle:group', props.item.data.id)"/></div>
        <template v-for="label, index in labels">
            <PropertyValueVue v-if="label.value" class="" :value="label.value" />
            <b v-else>{{ label.name }}</b>
            <div v-if="index < labels.length - 1" class="separator">&</div>
        </template>
    </div>
</template>

<style scoped>
.group-row {
    /* border-left: 1px solid var(--border-color); */
    border-right: 1px solid var(--border-color);
    border-bottom: 1px solid var(--border-color);
    box-sizing: border-box;
    background-color: rgb(249, 249, 249);
    padding-top: 2px;
    padding-left: 2px;
    line-height: 28px;
    position: relative;
    /* box-shadow: 0px 2px 3px var(--border-color); */
    /* z-index: 5; */
}

.separator {
    /* border-left: 2px solid var(--border-color); */
    margin: 0px 10px;
    color: gray;
}
</style>