<script setup lang="ts">
// The box every tree-cell property row lives in: property icon, then the value.
//
// It owns all the geometry and all the states, so the per-type inputs above it only decide
// what to render inside. Nothing is sized in pixels here: the frame is width:100% of whatever
// the cell gives it, so it can never be wider or narrower than its slot.
import PropertyIcon from '@/components/properties/PropertyIcon.vue'
import wTT from '@/components/tooltips/withToolTip.vue'
import { PropertyType } from '@/data/models'
import { Filter, FilterGroup, FilterOperator } from '@/core/FilterManager'
import { computed, inject, ref, watch } from 'vue'
import { useTabStore } from '@/data/stores/tabStore'
import { cellValueKey } from './cellValue'
import { useHoverSource } from '@/data/stores/hoverStore'

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
    // Full value for the hover tooltip, for rows whose rendering loses part of it (line breaks
    // drawn as icons, tags drawn as badges). Defaults to the text the value zone shows.
    tooltip?: string
}>()

const emits = defineEmits(['click', 'iconClick'])

// Exposed so an input that edits in a teleported popup (the multi-line text editor) can align
// that popup on the exact box its value occupies.
const valueZone = ref<HTMLElement>(null)
const root = ref<HTMLElement>(null)
const iconZone = ref<HTMLElement>(null)
defineExpose({ valueZone, root, iconZone })

// Every tree/cluster row funnels through this frame, so pointing at a property is reported
// once, here, rather than in each of the seven typed inputs. Outside those two scrollers no
// provider exists and the source reports nothing. Release on unmount is its job too.
const { enter, leave, setFocus } = useHoverSource(root)

// Focus, unlike hover, must survive the pointer wandering off: it lasts as long as the editor
// is open. Inline editors are caught by focusin/focusout on the row — and the claim is marked
// as living in the DOM, so the store can drop it by itself if the focusout never arrives (the
// number cell removes its <input> the instant it blurs). Editors whose focus lives in a
// teleported popup have nothing focused in the row and are driven by the `active` prop instead.
function onFocusIn() {
    setFocus(true, true)
}

function onFocusOut(e: FocusEvent) {
    // focus moving between two elements of the same row fires focusout then focusin: ignoring
    // the internal hop keeps the highlight from blinking.
    if (root.value?.contains(e.relatedTarget as Node)) return
    if (!props.active) setFocus(false)
}

watch(() => props.active, on => setFocus(on))

// Hovering a row shows its full value, but only when the row actually cuts it: a tooltip
// repeating what is already readable would pop up on every cell the pointer crosses. Never while
// an editor is open on the row, since the editor already shows the whole value.
const tip = ref(null)

function tooltipText() {
    const zone = valueZone.value
    if (!zone || props.empty || props.active || root.value?.matches(':focus-within')) return undefined
    if (!isClipped(zone)) return undefined
    return props.tooltip ?? zone.innerText.trim()
}

// The value zone and the values inside it each cut their own overflow with an ellipsis, so the
// cut can be on any of them.
function isClipped(zone: HTMLElement) {
    return [zone, ...Array.from(zone.querySelectorAll<HTMLElement>('*'))].some(e => e.scrollWidth > e.clientWidth)
}

// Copies the row's full value: the same text the tooltip would show, cut or not.
const copied = ref(false)
let copiedTimer: ReturnType<typeof setTimeout>

// Toggles "property = this value" ("contains" for tags) on the current tab's filters.
const cellValue = inject(cellValueKey, null)
const tabStore = useTabStore()
const filterManager = () => tabStore.getMainTab().collection.filterManager

// every filter of the tab on this row's property, nested groups included
function propertyFilters(): Filter[] {
    const propertyId = cellValue().propertyId
    const found: Filter[] = []
    const visit = (group: FilterGroup) => group.filters.forEach(f => {
        if (f.isGroup) visit(f as FilterGroup)
        else if ((f as Filter).propertyId == propertyId) found.push(f as Filter)
    })
    visit(filterManager().state.filter)
    return found
}

// Filled blue, as in the property panel, while any filter of the tab is on this property
const isFiltered = computed(() => !!cellValue && propertyFilters().length > 0)

// A second click removes the property's filters, matching the blue state above.
function filterValue() {
    const manager = filterManager()
    const existing = propertyFilters()
    if (existing.length) {
        existing.forEach(f => manager.deleteFilter(f.id))
        return
    }
    const { propertyId, value } = cellValue()
    const filter = manager.addNewFilter(propertyId)
    // tag properties have no "equal": match images that have all of the row's tags
    // (a single-tag property only offers "any", which is the same thing for one tag)
    const operator = props.type == PropertyType.multi_tags ? FilterOperator.containsAll
        : props.type == PropertyType.tag ? FilterOperator.containsAny
        : FilterOperator.equal
    manager.updateFilter(filter.id, { operator, value })
}

async function copyValue() {
    const text = props.tooltip ?? valueZone.value?.innerText.trim()
    if (!text) return
    await navigator.clipboard.writeText(text)
    copied.value = true
    clearTimeout(copiedTimer)
    copiedTimer = setTimeout(() => copied.value = false, 1000)
}
</script>

<template>
    <!-- pointerdown closes the tooltip: the click it starts opens an editor over the row -->
    <div class="tree-cell" ref="root" :class="{ active: props.active }" @click="emits('click')"
        @pointerenter="enter" @pointerleave="leave" @pointerdown="tip?.hide()" @focusin="onFocusIn"
        @focusout="onFocusOut">
        <!-- full-bleed layer under the icon and the value (colour fill) -->
        <!-- the icon's mousedown.prevent above keeps an open inline editor focused until its own
             click handler runs, so that click reads as a toggle rather than a blur then reopen -->

        <slot name="background" />
        <div v-if="!props.noIcon" class="icon-zone" ref="iconZone" :style="props.iconColor ? { color: props.iconColor } : undefined"
            @mousedown.prevent @click.stop="emits('iconClick')">
            <PropertyIcon :type="props.type" />
        </div>
        <!-- wTT has two root nodes, so this file's scoped styles can't reach its trigger span: the
             flex sizing that lets the value zone fill the row goes inline instead. A longer delay
             than wTT's default, since the pointer crosses rows constantly on its way elsewhere. -->
        <wTT ref="tip" :get-message="tooltipText" :delay="400" style="flex: 1 1 auto; min-width: 0;">
            <div class="value-zone" ref="valueZone">
                <slot />
                <!-- same "Vide..." the property previews show -->
                <span v-if="props.empty" class="empty">{{ $t('none') }}</span>
            </div>
        </wTT>
        <!-- mousedown.prevent keeps an open editor focused; click.stop keeps the row from opening one -->
        <span v-if="!props.empty && !props.active" class="row-actions">
            <!-- the styled span sits inside wTT: scoped styles can't reach wTT's own trigger span -->
            <wTT v-if="cellValue" message=".filter_by_value" :click="false">
                <span class="row-btn" @mousedown.prevent @click.stop="filterValue">
                    <i :class="isFiltered ? 'bi bi-funnel-fill text-primary' : 'bi bi-funnel'" />
                </span>
            </wTT>
            <wTT message=".copy" :click="false">
                <span class="row-btn" @mousedown.prevent @click.stop="copyValue">
                    <i :class="copied ? 'bi bi-check2' : 'bi bi-copy'" />
                </span>
            </wTT>
        </span>
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
    box-shadow: inset 0 0 0 1px var(--cell-blue);
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

.row-actions {
    position: absolute;
    right: 2px;
    top: 50%;
    transform: translateY(-50%);
    z-index: 2;
    display: none;
    background-color: white;
    border-radius: 3px;
}

.row-btn {
    padding: 0 3px;
    font-size: 12px;
    line-height: 18px;
    color: var(--grey-text);
}

.row-btn:hover {
    color: black;
}

/* only on hover, and never while the row is being edited */
.tree-cell:hover:not(:focus-within) .row-actions {
    display: inline-flex;
}

.empty {
    color: var(--text-secondary, #6c757d);
}
</style>
