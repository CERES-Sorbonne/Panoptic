<script setup lang="ts">
// The box every tree-cell property row lives in: property icon, then the value.
//
// It owns all the geometry and all the states, so the per-type inputs above it only decide
// what to render inside. Nothing is sized in pixels here: the frame is width:100% of whatever
// the cell gives it, so it can never be wider or narrower than its slot.
import PropertyIcon from '@/components/properties/PropertyIcon.vue'
import { PropertyType } from '@/data/models'
import { ref } from 'vue'

const props = defineProps<{
    type: PropertyType
    // Forces the active (blue) frame, for editors whose focus lives in a teleported popup
    // and therefore never triggers :focus-within here.
    active?: boolean
    // Renders the shared "Vide..." placeholder instead of a value.
    empty?: boolean
    // Drops the icon column, for types whose input already reads as the icon (checkbox).
    noIcon?: boolean
    // Overrides the icon colour, for rows that paint their own background behind it.
    iconColor?: string
}>()

const emits = defineEmits(['click', 'iconClick'])

// Exposed so an input that edits in a teleported popup (the multi-line text editor) can align
// that popup on the exact box its value occupies.
const valueZone = ref<HTMLElement>(null)
const root = ref<HTMLElement>(null)
const iconZone = ref<HTMLElement>(null)
defineExpose({ valueZone, root, iconZone })
</script>

<template>
    <div class="tree-cell" ref="root" :class="{ active: props.active }" @click="emits('click')">
        <!-- full-bleed layer under the icon and the value (colour fill) -->
        <slot name="background" />
        <div v-if="!props.noIcon" class="icon-zone" ref="iconZone" :style="props.iconColor ? { color: props.iconColor } : undefined"
            @click.stop="emits('iconClick')">
            <PropertyIcon :type="props.type" />
        </div>
        <div class="value-zone" ref="valueZone">
            <slot />
            <!-- same "Vide..." the property previews show -->
            <span v-if="props.empty" class="empty">{{ $t('none') }}</span>
        </div>
    </div>
</template>

<style scoped>
/* No border and no padding: the frame is drawn as an inset box-shadow, which paints inside
   the content box and so costs no geometry when it appears — showing it never moves the text.
   Transparent at rest so the cell's own edge ring shows through underneath. */
.tree-cell {
    display: flex;
    align-items: center;
    box-sizing: border-box;
    width: 100%;
    height: 26px;
    /* box-sizing: border-box above, and the frame is an inset shadow, so this costs no width */
    padding-left: 4px;
    padding-right: 1px;
    background-color: transparent;
    transition: background-color 0.2s;
    /* the cell ring (.img-border::after in Image.vue) is at z-index 4 and would cover the
       left/right pixel columns of a full-width row; sit above it */
    position: relative;
    z-index: 5;
    cursor: pointer;
    font-size: 14px;
    line-height: 18px;
}

/* The frame is drawn on an overlay rather than on the row itself, so it paints ABOVE the
   background slot (the colour fill). That fill can then run edge to edge instead of insetting
   itself by 1px, which read as a margin the other rows don't have. */
.tree-cell::after {
    content: '';
    position: absolute;
    inset: 0;
    box-shadow: inset 0 0 0 1px transparent;
    transition: box-shadow 0.2s;
    pointer-events: none;
    z-index: 1;
}

/* the theme's border colour on hover, blue once editing */
.tree-cell:hover {
    background-color: white;
}

.tree-cell:hover::after {
    box-shadow: inset 0 0 0 1px var(--border-color);
}

.tree-cell:focus-within,
.tree-cell.active {
    background-color: white;
}

.tree-cell:focus-within::after,
.tree-cell.active::after {
    box-shadow: inset 0 0 0 1px var(--blue);
}

/* positioned so they paint above the background slot, which is absolute */
.icon-zone {
    position: relative;
    flex: 0 0 auto;
    display: inline-flex;
    align-items: center;
    color: var(--grey-text);
    margin-right: 2px;
}

.icon-zone:hover {
    color: black;
}

/* min-width: 0 lets the value shrink below its natural width instead of pushing the frame
   wider than the cell */
.value-zone {
    position: relative;
    flex: 1 1 auto;
    min-width: 0;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
}

.empty {
    color: var(--text-secondary, #6c757d);
}
</style>
