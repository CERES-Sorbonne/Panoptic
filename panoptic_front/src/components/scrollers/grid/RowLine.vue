<script setup lang="ts">
import Zoomable from '@/components/Zoomable.vue';
import CenteredImage from '@/components/images/CenteredImage.vue';
import SelectCircle from '@/components/inputs/SelectCircle.vue';
import type { GroupInspector } from '@/core/group/inspector'
import { ModalId, Property, PropertyType } from '@/data/models';
import { PileRowLine, RowLine } from '@/components/scrollers/types';
import { usePanopticStore } from '@/data/stores/panopticStore';
import { useColumnStore } from '@/data/stores/columnStore';
import { emptyInstanceEntry, useInstanceStore } from '@/data/stores/instanceStore';
import { computed, inject, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import GridPropInput from './GridPropInput.vue';
import GridCellView from './GridCellView.vue';
import { TabManager } from '@/core/TabManager';
import { isTag } from '@/utils/utils';
import { CellKey, cellEditingKey, openPropertiesOf, useCellEditing } from '../cellEditing';
import { rowHeightsKey } from './rowHeights';

const panoptic = usePanopticStore()
const columnStore = useColumnStore()

const props = defineProps<{
    tab: TabManager,
    imageSize: number,
    manager: GroupInspector,
    item: any,
    properties: Property[],
    showImage: boolean,
    selected?: boolean,
    missingWidth: number,
    // The least height of the row (the image, or one line), which is also GridScroller's size for
    // rows not measured yet. The row grows to fit its cells.
    rowHeight: number,
    // expandImage: boolean
}>()
const emits = defineEmits({
    'toggle:image': Object,
})

const tab = computed(() => props.tab.state)
const instanceId = computed(() => {
    if (props.item.type == 'pile') {
        const handle = (props.item as PileRowLine).data
        return columnStore.instanceIds()[handle.slots[0]]
    }
    return (props.item as RowLine).data.id
})

// Use the reactive instance from the store so property values populated by
// InstanceData (via register) are reflected here without an extra fetch.
const image = computed(() =>
    useInstanceStore().instanceData[instanceId.value] ?? emptyInstanceEntry(instanceId.value)
)

// The group the row is drawn in: part of a cell's identity, the same image can be in several.
const groupId = computed(() => props.item.type == 'pile' ? (props.item as PileRowLine).data.groupId : (props.item as RowLine).groupId)

// Cells are drawn read-only (GridCellView); the scroller says which of them have their editor
// (GridPropInput) open. Outside a GridScroller the row keeps its own state, so it still edits.
const cells = inject(cellEditingKey, null) ?? useCellEditing()

// This row's open properties. Every row re-evaluates when a cell opens or closes: handing back the
// previous array while nothing changed for this row keeps it from re-rendering.
const openIds = computed<number[]>(previous => openPropertiesOf(cells.open.value, instanceId.value, groupId.value, previous))

// Each column with its cell key, captured at render: the editor's close/tab handlers must name
// the cell it was opened on, even when it reports after the row was recycled to another image.
const columns = computed(() => props.properties.map(property => ({
    property,
    key: { instanceId: instanceId.value, groupId: groupId.value, propertyId: property.id } as CellKey,
})))

// The types GridPropInput has an editor for. A checkbox toggles in its read-only cell instead.
function hasEditor(type: PropertyType) {
    return isTag(type) || type == PropertyType.string || type == PropertyType.url || type == PropertyType.color
        || type == PropertyType.date || type == PropertyType.number
}

function openCell(key: CellKey, property: Property) {
    if (hasEditor(property.type)) cells.openCell(key)
}

// The row is measured whole, by its scroller (rowHeights.ts): its root is observed for as long as
// it is mounted, and measured again when the scroller recycles it to another line. Outside a
// GridScroller nothing measures it; it still fits its content.
const rowHeights = inject(rowHeightsKey, null)
const rowElem = ref<HTMLElement | null>(null)
onMounted(() => { if (rowElem.value) rowHeights?.observe(rowElem.value, () => props.item) })
onBeforeUnmount(() => { if (rowElem.value) rowHeights?.unobserve(rowElem.value) })
watch(() => props.item, () => { if (rowElem.value) rowHeights?.remeasure(rowElem.value) }, { flush: 'post' })

const pile = computed(() => {
    if (props.item.type == 'pile') {
        return (props.item as PileRowLine).data
    }
    return undefined
})

// The min-height every cell's content is drawn at: the row's least height less the cell's 2px
// padding above and below and its 1px bottom border, so the fixed-height values (a color, a folder)
// fill a row exactly and an unmeasured row's estimate is its real height. (It was the full row
// height with images, 24px without: those cells made their row 1-5px taller than its estimate.)
// A constant, never the measured height of the row or of another cell: the row's height comes from
// its content alone (the cells are stretched to the tallest in CSS), so measuring it cannot echo
// back what it was assigned.
const cellMinHeight = computed(() => props.rowHeight - 5)

const inputWidth = computed(() => {
    const res = {} as { [propId: string]: number }
    props.properties.forEach(p => {
        res[p.id] = tab.value.propertyOptions[p.id].size - 7
        if (p.id == props.properties[props.properties.length - 1].id) {
            // The scrollbar is already excluded from missingWidth by GridScroller.
            if (props.missingWidth > 0) res[p.id] += props.missingWidth
        }
    })
    return res
})

const classes = computed(() => {
    const res = ['header-cell']
    if (props.item.index == 0) {
        res.push('top-border')
    }
    return res
})


function showModal() {
    let iterator
    if (props.item.type === 'pile') {
        const handle = (props.item as PileRowLine).data
        iterator = props.manager.getImageIterator(handle.groupId, handle.pileIndex)
    } else {
        const rowItem = props.item as RowLine
        iterator = props.manager.getImageIterator(rowItem.groupId, rowItem.index)
    }
    // A recycled line can outlive its group; an invalid iterator has no slot, and the modal
    // would open on nothing.
    if (!iterator?.isValid) return
    panoptic.showModal(ModalId.IMAGE, iterator)
}
</script>


<template>
    <!-- min-height only: the row is as tall as its tallest cell. No height of its own, no item.size,
         no height: 100% (see cellMinHeight). -->
    <div class="d-flex row-line" :style="{ minHeight: props.rowHeight + 'px' }" ref="rowElem">
        <!-- <div class="left-border" :style="{ height: props.item.size + 'px' }"></div> -->
        <div v-if="showImage" :class="classes" :style="{
            width: (props.imageSize) + 'px', position: 'relative', cursor: 'pointer',
        }" class="p-0 m-0 image-cell" @click="showModal">
            <Zoomable :image="image">
                <!-- rowHeight - 4: the cell's 3px top padding and 1px bottom border (GridScroller's
                     imageSize + 4). Any taller and every image row would measure taller than the
                     size it is laid out at, and be corrected on each mount. -->
                <CenteredImage :instance-id="image.id" :width="props.imageSize - 1" :height="props.rowHeight - 4" />
                <!-- Shown on CSS :hover rather than a mouseenter flag, which goes stale when the
                     scroller recycles this row (see tree/Image.vue). -->
                <div class="h-100 box-shadow" :class="{ 'hover-only': !props.selected }" :style="{ width: props.imageSize + 'px' }"
                    style="position: absolute; top:0; left:0; right: 0px; bottom: 0px;"></div>
                <SelectCircle :model-value="props.selected" :class="{ 'hover-only': !props.selected }"
                    @update:model-value="v => emits('toggle:image', { groupId: item.groupId, imageIndex: item.index })"
                    class="select" :light-mode="true" />
                <div class="image-count num" v-if="pile?.slots.length > 1">{{ pile.slots.length }}</div>
            </Zoomable>
        </div>

        <!-- Cells ignore update:height: the row is measured whole. The editor shows the whole value
             (tags wrapped, like at rest) and the row grows with it as it is typed in. -->
        <div v-for="col in columns" :key="col.property.id" class="container22 cell"
            :style="{ width: inputWidth[col.property.id] + 7 + 'px' }"
            style="padding: 0px 3px; font-size: 14px;" @click="openCell(col.key, col.property)">
            <GridPropInput v-if="openIds.includes(col.property.id)" :open="true" :instance="image"
                :property="col.property" :min-height="cellMinHeight" :width="inputWidth[col.property.id]"
                @click.stop="" @close="cells.closeCell(col.key)"
                @tab="backwards => cells.tab(col.key, backwards)" />
            <GridCellView v-else :instance="image" :property="col.property" :min-height="cellMinHeight"
                :width="inputWidth[col.property.id]" />
        </div>

        <!-- With no properties shown there is no column to absorb the leftover
             width, so the row would stop at the image and lose its borders. -->
        <div v-if="!props.properties.length && props.missingWidth > 0" class="container22"
            :style="{ width: props.missingWidth + 'px' }"></div>
    </div>
</template>

<style scoped>
/* Columns keep their exact width even when the row is wider than the viewport,
   so they stay aligned with the (non-flex, inline-block) table header. */
.row-line > * {
    flex-shrink: 0;
}

.image-count {
    position: absolute;
    top: 0;
    right: 0;
    padding: 0px 4px;
    background-color: var(--border-color);
    color: var(--grey-text);
    font-size: 10px;
    line-height: 15px;
    margin: 2px;
    border-radius: 5px;
    z-index: 100;
}

.select {
    position: absolute;
    top: 0;
    left: 5px;
}

.left-border {
    border-left: 1px solid var(--border-color);
    display: inline-block;
    width: 1px;
    /* height: 100%; */
}

.container22 {
    border-right: 1px solid var(--border-color);
    border-bottom: 1px solid var(--border-color);
}

/* Cells keep their column's width; the row is as tall as its tallest cell, so nothing is cut
   vertically (the values cap themselves, see GridCellView). The cell being edited is let out of
   its clip so the editor's focus shadow is not cut, and GridScroller raises its row above the
   next one, which would paint over it. Editors that open a popup (tags, color, date) teleport
   it and are not concerned. */
.cell {
    overflow: hidden;
}

.cell:focus-within {
    overflow: visible;
}

.header-cell {
    vertical-align: top;
    border-left: none;
    border-right: 1px solid var(--border-color);
    border-bottom: 1px solid var(--border-color);
    /* overflow: hidden; */
    /* resize: horizontal; */
    padding-top: 3px;
    padding-left: 3px;
    margin: 0;
    display: inline-block;
    /* box-sizing: content-box; */
    /* cursor:text; */
    /* border-top: 1px solid red; */
}

.prop-input {
    margin: 3px;
}

.top-border {
    border-top: none;
}


.image-cell:not(:hover) .hover-only {
    visibility: hidden;
}

.box-shadow {
    position: relative;
}

.box-shadow::after {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 1px;
    height: 100%;
    -webkit-box-shadow: inset 0px 50px 30px -30px rgba(0, 0, 0, 0.5);
    -moz-box-shadow: inset 0px 50px 30px -30px rgba(0, 0, 0, 0.5);
    box-shadow: inset 0px 50px 30px -30px rgba(0, 0, 0, 0.5);
    overflow: hidden;
}
</style>