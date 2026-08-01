<script setup lang="ts">
import { computed, inject, ref } from 'vue'
import SelectCircle from '@/components/inputs/SelectCircle.vue'
import wTT from '../../tooltips/withToolTip.vue'
import { ImageIterator } from '@/core/GroupManager'
import { ModalId, Property } from '@/data/models'
import { usePanopticStore } from '@/data/panopticStore'
import Zoomable from '@/components/Zoomable.vue'
import CenteredImage from '@/components/images/CenteredImage.vue'
import TreePropertyInput from './TreePropertyInput.vue'
import { useColumnStore } from '@/data/columnStore'
import { useInstanceStore } from '@/data/instanceStore.js'
import { useDataStore } from '@/data/dataStore'

const panoptic = usePanopticStore()
const store = useColumnStore()
const data = useDataStore()

const props = defineProps({
    image: { type: ImageIterator, required: true },
    size: { type: Number, default: 100 },
    // Optional per-cell width (defaults to `size`). The scroller hands out 1px-wider
    // widths to some cells so a line fills its full width; height stays driven by `size`.
    width: { type: Number, default: undefined },
    index: Number,
    groupId: Number,
    hideProperties: Boolean,
    constraintWidth: Boolean,
    noBorder: Boolean,
    properties: Array<Property>,
    selected: Boolean,
    selectedPreview: Boolean
})

const emits = defineEmits(['resize', 'update:selected'])

// Cell width: the scroller-provided width when set, otherwise a square `size` cell.
const w = computed(() => props.width ?? props.size)

// ── RESOLVE INSTANCE ID FROM SLOT ───────────────────────────────────────────
const instanceId = computed(() => store.instanceIds()[props.image.slot])

// Reactive per-instance property values (for TreePropertyInput).
// FIX 1: Provide a structural fallback value (-1) to keep the type checks happy before data streams in
const inst = computed(() => {
    const id = instanceId.value
    if (id === undefined || isNaN(id)) {
        return { id: -1, properties: {} }
    }
    return useInstanceStore().instanceData[id] ?? { id: id, properties: {}, baseUrl: '', sha1: '' }
})

const isSelected = computed(() => props.selected ?? false)

const hover = ref(false)
const hideImg = inject('hideImg')
const inputKey = inject('inputKey') as string

const score = computed(() => {
    const group = props.image.group
    if (!group.scores || instanceId.value === undefined) return undefined
    return group.scores.valueIndex[instanceId.value]
})
</script>

<template>
    <div class="full-container" :class="[!props.noBorder ? 'img-border' : '', isSelected ? 'selected' : '']"
        :style="`width: ${w + 2}px;`">
        <Zoomable v-if="!hideImg && instanceId !== undefined" :image="inst">
            <div class="img-container" :style="`width: ${w + 2}px; height: ${props.size}px;`"
                @click="panoptic.showModal(ModalId.IMAGE, props.image)" @mouseenter="hover = true"
                @mouseleave="hover = false">
                <div v-if="score != undefined" class="simi-ratio">{{ score }}</div>
                <CenteredImage :instance-id="instanceId" :width="w" :height="props.size"
                    style="position: absolute; top: 0" />

                <!-- overlay follows the container instead of being sized in px, so it can
                     never exceed the clipped (and rounded) image area -->
                <div v-if="hover || isSelected" class="box-shadow" />
                <SelectCircle v-if="hover || isSelected" :model-value="isSelected"
                    @update:model-value="v => emits('update:selected', v)" class="select" :light-mode="true" />
            </div>
        </Zoomable>

        <!-- Spinner only while the instance base is still streaming; once loaded an
             unresolved slot means an empty group, so render nothing instead. -->
        <div v-else-if="!hideImg && !data.isLoaded"
            class="d-flex align-items-center justify-content-center bg-light text-muted border border-secondary-subtle"
            :style="`width: ${w + 2}px; height: ${props.size}px;`">
            <div class="spinner-border spinner-border-sm text-secondary" role="status"></div>
        </div>

        <!-- Absolutely-positioned wrapper: keeps the tooltip trigger span out of normal
             flow so it doesn't add an empty line box (which would overflow the row). -->
        <div v-if="props.image.slots?.length > 1" class="image-count-wrap">
            <wTT message="main.view.instances_tooltip" :click="false">
                <div class="image-count">{{ props.image.slots.length }}</div>
            </wTT>
        </div>

        <div class="prop-container" v-if="props.properties.length && !props.hideProperties && instanceId !== undefined">
            <TreePropertyInput v-for="property in props.properties" :key="property.id"
                :group-id="props.image.groupId" :input-key="inputKey" :property="property" :instance="inst"
                :idx="props.image.getImageOrder()" />
        </div>

        <div v-if="props.selectedPreview" class="w-100 h-100"
            style="position: absolute; top: 0; left: 0; background-color: rgba(0, 0, 255, 0.127);" />
    </div>
</template>
<style scoped>
.image-count-wrap {
    position: absolute;
    top: 0;
    right: 0;
    z-index: 100;
}

/* Count / score chips: dark pills that read on any image, as on the cluster cards. */
.image-count {
    padding: 1px 5px;
    background: rgba(0, 0, 0, 0.55);
    color: #fff;
    font-size: 10px;
    line-height: 13px;
    margin: 4px;
    border-radius: 999px;
    white-space: nowrap;
}

.simi-ratio {
    position: absolute;
    bottom: 0;
    right: 0;
    padding: 1px 5px;
    background: rgba(0, 0, 0, 0.55);
    color: #fff;
    font-size: 10px;
    line-height: 13px;
    margin: 4px;
    border-radius: 999px;
    z-index: 100;
}

/* Photo card, same shape as the cluster view's card: rounded box clipping the image, a
   surface behind it, and the ring drawn on top as an inset overlay (see .img-border). */
.full-container {
    position: relative;
    display: flex;
    flex-direction: column;
    /* No surface of its own: the property rows show the view's background through. */
    background-color: transparent;
    border-radius: 3px;
    overflow: hidden;
    /* No margin here: the line comps apply me-2/mb-2, which is the GAP the scroller budgets
       for (TreeScroller.fillWidths). A margin of our own would be spent twice, overflow the
       line, and get taken back out of the cards by flex-shrink. */
    /* The cell width is computed to the pixel by the scroller: never let flex resize it.
       min-width:0 also drops the automatic min-content floor — without it a card could not
       shrink below the intrinsic width of whatever input its property rows render, so
       focusing a row (span -> <input>) visibly widened the card. */
    flex: 0 0 auto;
    min-width: 0;
}

/* Ring as an inset overlay rather than a real border: it stays inside the cell's own width
   (no bleed into the neighbour, and the cell keeps the size the scroller computed) and paints
   above the image and its hover overlays, so the top edge stays visible. */
.img-border::after {
    content: '';
    position: absolute;
    inset: 0;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    pointer-events: none;
    z-index: 4;
}

/* Selected cell: the ring itself turns primary, instead of adding a second outline. */
/* Above everything the card contains — the property rows sit at z-index 5 so their hover
   frames and full-bleed colour fills would otherwise cut across the selection ring. */
.img-border.selected::after {
    border: 2px solid var(--primary, #4f46e5);
    z-index: 10;
}

.img-container {
    position: relative;
    margin: auto;
    padding: auto;
    cursor: pointer;
    background-color: var(--bg-subtle, #f3f4f6);
    overflow: hidden;
    /* the image is the card's top edge: match the ring's corners (4px minus the 1px ring), or
       the hover shadow squares off past them */
    border-top-left-radius: 3px;
    border-top-right-radius: 3px;
}

.prop-container {
    width: 100%;
    box-sizing: border-box;
    /* No inset: the property rows run the full width of the card and paint over its edge ring
       (.img-border::after) rather than tucking inside it. */
    /* border-top: 1px solid var(--border-color); */
    /* padding: 4px; */
    padding-top: 0px;
    padding-bottom: 0px;
    font-size: 12px;
}

/* The bottom row is the card's bottom edge: follow the card ring's corners (4px, minus the
   1px ring itself) instead of running square into them. Covers the row's surface, its
   hover/focus overlay and any full-bleed fill (the colour chip). */
.prop-container :deep(> :last-child.tree-cell),
.prop-container :deep(> :last-child.tree-cell::after),
.prop-container> :last-child :deep(.tree-cell),
.prop-container> :last-child :deep(.tree-cell::after),
.prop-container> :last-child :deep(.chip) {
    border-bottom-left-radius: 3px;
    border-bottom-right-radius: 3px;
}

.select {
    position: absolute;
    top: 0;
    left: 5px;
}

.box-shadow {
    position: absolute;
    /* the container spans the card's full width (w + 2) while the image inside is only w wide,
       so a full-bleed overlay tints the ring's own pixel columns: stay 1px in */
    inset: 1px;
    pointer-events: none;
}

.box-shadow::after {
    content: '';
    position: absolute;
    inset: 0;
    -webkit-box-shadow: inset 0px 24px 25px -20px rgba(0, 0, 0, 0.3);
    -moz-box-shadow: inset 0px 24px 25px -20px rgba(0, 0, 0, 0.3);
    box-shadow: inset 0px 50px 30px -30px rgba(0, 0, 0, 0.5);
    overflow: hidden;
}
</style>
