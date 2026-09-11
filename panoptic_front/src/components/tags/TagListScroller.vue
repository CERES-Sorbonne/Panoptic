<script setup lang="ts">

/**
 * Virtualized tag list.
 *
 * Same row markup as the plain v-for it replaces, but only the rows in view are mounted.
 * That matters because every row carries two floating-vue dropdowns (options + child link),
 * each with its own popper instance, observers and listeners: rendering a property's whole
 * tag list made opening the menu cost O(tags) and took hundreds of ms on large properties.
 * With the scroller the cost is bounded by the viewport (~12 rows), whatever the tag count.
 *
 * Rows are a fixed height, so RecycleScroller gets a constant :item-size and needs no
 * measuring pass. Keep ROW_HEIGHT in sync with the .tag-row CSS below.
 */

import { computed, ref } from 'vue';
import TagBadge from '../tagtree/TagBadge.vue';
import TagOptionsDropdown from '../dropdowns/TagOptionsDropdown.vue';
import TagChildSelectDropdown from '../dropdowns/TagChildSelectDropdown.vue';
import { RecycleScroller } from 'vue-virtual-scroller';
import { deletedID, Property, Tag } from '@/data/models';
import { useDataStore } from '@/data/dataStore';
import { sum } from '@/utils/utils';

const data = useDataStore()

const props = withDefaults(defineProps<{
    property: Property,
    tags: Tag[],
    // Highlighted row (hover or keyboard). undefined = nothing highlighted.
    selectedIndex?: number,
    canLink?: boolean,
    canCustomize?: boolean,
    canDelete?: boolean,
    maxHeight?: number
}>(), { maxHeight: 300 })

const emits = defineEmits(['select', 'delete', 'hide', 'update:selectedIndex'])

// padding (3 + 3) + the row's 20px line-height
const ROW_HEIGHT = 26

const scroller = ref(null)

defineExpose({ scrollToIndex })

// One viewport tall at most; shorter when there are fewer tags than that, so the menu does
// not reserve empty space under a two-tag property.
const viewportHeight = computed(() => Math.min(props.maxHeight, Math.max(ROW_HEIGHT, props.tags.length * ROW_HEIGHT)))

// Own count + the counts of every descendant, computed once per list change rather than once
// per row per render: the inline expression re-walked allChildren on each hover.
const totalCounts = computed(() => {
    const res: { [tagId: number]: number } = {}
    for (const tag of props.tags) {
        res[tag.id] = tag.count + sum(tag.allChildren.map(c => data.tags[c] && data.tags[c].id != deletedID ? data.tags[c].count : 0))
    }
    return res
})

// Scroll the row into view by the smallest amount that makes it fully visible. Deliberately
// NOT scrollToItem (which always aligns the row to the top) and deliberately not driven by a
// watch on selectedIndex: hover sets selectedIndex too, and scrolling on hover moves the list
// under the cursor, which fires mouseover on another row and runs away down the list. Only
// keyboard navigation calls this.
function scrollToIndex(index: number) {
    const el = scroller.value?.$el
    if (index == undefined || !el) return
    const top = index * ROW_HEIGHT
    const bottom = top + ROW_HEIGHT
    if (top < el.scrollTop) el.scrollTop = top
    else if (bottom > el.scrollTop + el.clientHeight) el.scrollTop = bottom - el.clientHeight
}

function setSelected(index: number) {
    emits('update:selectedIndex', index)
}

// Only clear the highlight if this row still owns it: the mouseleave of the row being left
// can arrive after the mouseover of the row being entered.
function endSelection(index: number) {
    if (props.selectedIndex == index) emits('update:selectedIndex', undefined)
}

const rowClass = (index: number) => props.selectedIndex == index ? 'bg-selected' : 'bg-white'

</script>

<template>
    <RecycleScroller class="tag-list" ref="scroller" :items="props.tags" key-field="id" :item-size="ROW_HEIGHT"
        :buffer="ROW_HEIGHT * 4" :style="{ height: viewportHeight + 'px' }">
        <template v-slot="{ item, index }">
            <div :class="[rowClass(index), 'tag-row']" style="cursor: pointer;" @mouseover="setSelected(index)"
                @mouseleave="endSelection(index)">
                <div class="ms-2 d-flex align-items-center">
                    <div class="flex-grow-1" style="overflow: hidden;" @click="emits('select', index)">
                        <TagBadge :id="item.id" />
                    </div>
                    <div v-if="props.canLink"
                        :style="{ color: (props.selectedIndex == index) ? 'var(--text-color)' : 'white' }">
                        <TagChildSelectDropdown :property-id="item.propertyId" :tag-id="item.id"
                            @hide="emits('hide')" />
                    </div>
                    <div v-if="props.canCustomize || props.canDelete"
                        :style="{ color: (props.selectedIndex == index) ? 'var(--text-color)' : 'white' }">
                        <TagOptionsDropdown :property-id="props.property.id" :tag-id="item.id"
                            :can-delete="props.canDelete" :can-customize="props.canCustomize"
                            @delete="id => emits('delete', id)" @hide="emits('hide')" />
                    </div>
                    <div class="text-secondary" style="font-size: 10px; line-height: 20px; padding-right: 2px;">
                        {{ totalCounts[item.id] }}
                    </div>
                </div>
            </div>
        </template>
    </RecycleScroller>
</template>

<style scoped>
.tag-list {
    overflow-y: auto;
}

/* A row is a badge with room around it, not a line of text: without this the badges stack edge
   to edge and read as one block. The padding is what separates them; the badge itself is then
   centred in the row it sits in. Total height must stay ROW_HEIGHT. */
.tag-row {
    /* pulled 4px out on each side and given the same back as padding: the row's highlight runs
       wider than its content instead of hugging the badge, while the badge itself does not move */
    margin: 0 -4px;
    padding: 3px 4px;
    border-radius: 3px;
    box-sizing: border-box;
    height: 26px;
}
</style>
