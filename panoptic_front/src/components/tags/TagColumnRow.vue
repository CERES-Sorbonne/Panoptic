<script setup lang="ts">
// One row of a TagColumn. Hover state lives here, not in the column: a column holds every tag of
// a property without virtualization, and a column-level hover ref made each mouseenter/mouseleave
// re-render all of its rows. Here a hover re-renders this row only, and rows whose props did not
// change are skipped when the column does re-render (selection, sort, filter).
import TagOptionsDropdown from '@/components/dropdowns/TagOptionsDropdown.vue';
import TagBadge from '@/components/tagtree/TagBadge.vue';
import { Tag } from '@/data/models';
import { ref } from 'vue'

const props = defineProps<{
    tag: Tag
    selected: boolean
    count: number
    noCreate?: boolean
}>()
const emits = defineEmits(['select', 'delete'])

const hovered = ref(false)
// options popup open: keeps the row buttons (and so the popup) mounted after the mouse leaves the row
const optionsOpen = ref(false)
</script>

<template>
    <div class="tag-row d-flex align-items-center ps-2" :class="props.selected ? 'bg-blue' : (hovered ? 'bg-selected' : '')"
        style="cursor: pointer;" @click="emits('select', props.tag)"
        @mouseenter="hovered = true" @mouseleave="hovered = false">

        <div class="overflow-hidden">
            <TagBadge :id="props.tag.id" />
        </div>
        <div class="flex-grow-1" style="margin-left: 2px;"></div>
        <div v-if="hovered || optionsOpen" class="row-actions d-flex align-items-center" @click.stop>
            <div v-if="!props.noCreate"><i class="bi bi-trash sm-btn" @click.stop="emits('delete', props.tag)"></i></div>
            <TagOptionsDropdown :property-id="props.tag.propertyId" :tag-id="props.tag.id"
                :can-customize="true"
                @show="optionsOpen = true" @hide="optionsOpen = false" />
        </div>
        <div class="me-2 text-secondary num" style="font-size: 13px;">{{ props.count }}</div>
    </div>
</template>

<style scoped>
/* same row spacing as TagListScroller: padding keeps the badges from stacking edge to edge */
.tag-row {
    padding-top: 3px;
    padding-bottom: 3px;
}

/* delete and options icons: same line box, centred on the row. The options icon carries its own
   1.5px nudge (tuned for other lists), cancelled here so both icons share one centre line. */
.row-actions,
.row-actions :deep(i) {
    line-height: 1;
}

.row-actions :deep(.bi-three-dots) {
    top: 0 !important;
}

.bg-blue {
    background-color: rgba(89, 89, 247, 0.309);
}
</style>
