<script setup lang="ts">
// Tag property row of a tree cell. The tag picker itself is the shared TagInput (tag creation,
// linking, colours — far more than a row shell should own); this owns only the cell side: the
// badges while reading, and the popup the picker opens in.
//
// It does NOT go through CellTagInput/Dropdown: that pair places the popup as a generic dropdown
// (below the button, nudged by a magic offset), whereas a tree cell's editor must be parked ON
// the cell it edits — same placement as the text editor, see cellPopup.ts.
import { nextTick, onBeforeUnmount, ref } from 'vue'
import TreeCellFrame from './TreeCellFrame.vue'
import PropertyIcon from '@/components/properties/PropertyIcon.vue'
import TagBadge from '@/components/tagtree/TagBadge.vue'
import TagInput from '@/components/property_inputs/TagInput.vue'
import { useCellPopup } from './cellPopup'
import { Property, PropertyType } from '@/data/models'

const props = defineProps<{
    modelValue?: any
    property: Property
    instanceId: number
    // Single-tag behaviour even for a multi-tag property (group-level editing in the cluster view).
    forceMono?: boolean
}>()

const emits = defineEmits(['update:modelValue', 'focus', 'blur', 'tab'])

const frame = ref(null)
const contentElem = ref(null)
const inputElem = ref(null)
const editing = ref(false)
// The user's working selection while the popup is open — see updateValue: the committed value
// only lands on close, and props.modelValue must not overwrite this mid-edit.
const localValue = ref<number[]>([])

const { popup, popupElem, place, setWidth, fit, watchViewport, stopWatch } = useCellPopup(frame)

// The picker is a menu, not text: it has no natural width to grow to, so it takes one fixed
// width (the cell's, when that is already wider) and keeps it for the whole edit — a picker that
// resized as the search filtered its list would be unusable.
const PICKER_WIDTH = 200
// Nudge for the picker alone — the text editor keeps sitting exactly on its cell. Only the BOX
// moves: the horizontal part is given back as width and as a left padding on the content, so the
// icon and the first badge stay on the pixels the cell put them on and the right edge stays on
// the cell's — x reads as an overhang, not as a shift of what's inside.
// x < 0 reaches past the cell's left edge, y > 0 drops the picker below the cell's top.
const OFFSET = { x: -4, y: 0 }

const tags = () => (props.modelValue ?? []) as number[]

// Mono when the property is single-tag, or when the caller forces it: a pick replaces the value
// and closes, as in CellTagInput.
const isMono = () => props.forceMono || props.property.type == PropertyType.tag

async function focus() {
    if (editing.value) return
    // a copy: the picker edits localValue in place, and props.modelValue must survive a cancel
    localValue.value = [...(props.modelValue ?? [])]
    editing.value = true
    place()
    setWidth(PICKER_WIDTH, PICKER_WIDTH)
    popup.value.left += OFFSET.x
    popup.value.top += OFFSET.y
    popup.value.width -= OFFSET.x
    // absolutely positioned, so it is placed from the box's own corner and the content's padding
    // never reaches it: it pays the shift back itself
    popup.value.icon.left -= OFFSET.x
    emits('focus')
    await nextTick()
    inputElem.value?.focus()
    fit(contentElem.value)
    watchViewport(close)
    window.addEventListener('keydown', onKeyDown, true)
}

// Escape discards: the selection only ever lived in localValue, so closing without emitting is
// the whole of the cancel. Listened for on the window rather than on the popup — parts of the
// picker (the tag menu) teleport out of it, and a key pressed there would never reach it.
function onKeyDown(e: KeyboardEvent) {
    if (e.key != 'Escape') return
    e.stopPropagation()
    close(false)
}

// Order-insensitive: the picker rebuilds the list on every pick, so a value that came back to the
// same set of tags is not a change.
function sameTags(a: number[], b: number[]) {
    if (a.length != b.length) return false
    const set = new Set(a)
    return b.every(id => set.has(id))
}

function close(commit = true) {
    if (!editing.value) return
    editing.value = false
    stopWatch()
    window.removeEventListener('keydown', onKeyDown, true)
    // Only a real change is committed: merely opening and closing the picker must not write the
    // cell (an empty cell would be sent an empty value, which still counts as an edit downstream).
    if (commit && !sameTags(localValue.value, props.modelValue ?? [])) {
        emits('update:modelValue', localValue.value)
    }
    emits('blur')
}

function onClick() {
    // the row toggles: a second click on it (or on its icon) closes the picker again
    if (editing.value) return close()
    focus()
}

function updateValue(value: number[]) {
    localValue.value = value
    if (isMono()) return close()
    // the list grows and shrinks with the selection, so the popup has to be re-fitted
    nextTick(() => fit(contentElem.value))
}

function onTab() {
    emits('tab')
    close()
}

onBeforeUnmount(() => window.removeEventListener('keydown', onKeyDown, true))

defineExpose({ focus })
</script>

<template>
    <TreeCellFrame ref="frame" :type="props.property.type" :active="editing" :empty="!tags().length" @click="onClick"
        @icon-click="onClick">
        <div class="badges">
            <TagBadge v-for="id in tags()" :key="id" :id="id" class="me-1" />
        </div>
    </TreeCellFrame>

    <Teleport to="body">
        <div v-if="editing" ref="popupElem" class="cell-popup tag-popup"
            :style="{ ...popup.text, top: popup.top + 'px', left: popup.left + 'px', width: (popup.width + popup.scrollbar) + 'px',  maxHeight: popup.maxHeight ? popup.maxHeight + 'px' : undefined }">
            <!-- Same icon, same toggle: it closes the picker it opened. mousedown.prevent so the
                 close is this click's doing rather than the focus loss it would cause first. -->
            <div class="popup-icon" @mousedown.prevent @click="close()"
                :style="{ top: popup.icon.top + 'px', left: popup.icon.left + 'px', width: popup.icon.width + 'px', height: popup.icon.height + 'px', fontSize: popup.icon.fontSize }">
                <PropertyIcon :type="props.property.type" />
            </div>
            <!-- Full width, not inset to the value box: the picker's tinted header is a surface,
                 and a surface must run under the icon column too, exactly as the cell's colour
                 fill does. Its CONTENT is what keeps the cell's alignment, via --cell-indent. -->
            <div ref="contentElem" class="tag-content"
                :style="{ paddingLeft: -OFFSET.x + 'px', '--cell-indent': popup.contentLeft + 'px', '--cell-pad-top': popup.padTop + 'px' }">
                <TagInput ref="inputElem" :property="props.property" :model-value="localValue"
                    :instance-id="props.instanceId" :can-create="true" :can-customize="true" :auto-focus="true"
                    :force-mono="props.forceMono" @update:model-value="updateValue" @tab="onTab" />
            </div>
        </div>
    </Teleport>
</template>

<style scoped>
/* A menu, not a field: it reads as a surface lifted off the page rather than as the cell turned
   editable, so it takes a deeper shadow than the text editor. Same edge, more elevation. */
.tag-popup {
    box-shadow: 0 8px 24px rgba(0, 123, 255, 0.18), 0 2px 8px rgba(0, 0, 0, 0.16);
    border-radius: 5px;
    /* the tinted header runs to the popup's own edges, corners included */
    overflow: hidden auto;
}

/* The header's tint runs edge to edge (icon column included); only what it contains is pushed
   back to the column the cell's value occupies, so nothing appears to move on opening. */
.tag-content :deep(.selection),
.tag-content :deep(.search-row) {
    padding-left: var(--cell-indent);
}

/* the header's own top inset replaced by the cell's, so the first badge sits as far from the
   popup's top edge as the preview's does from the cell's */
.tag-content :deep(.selection) {
    padding-top: var(--cell-pad-top);
}

/* The list is the popup's own content, not a continuation of the cell: it keeps a small, even
   inset of its own rather than the cell's indent, which would leave it hanging off centre. */
.tag-content :deep(.list-hint) {
    padding-left: 8px;
}

.tag-content :deep(.tag-list) {
    padding: 2px 4px 8px;
}

/* the list's own bottom inset is inside its scroll box, so the popup needs one of its own to
   keep the last row off the edge */
.tag-content {
    /* the popup IS the picker: the surface fills it, only the content is inset (--cell-indent) */
    width: 100%;
    padding-bottom: 6px;
}

/* One line of badges, clipped by the cell like every other value row */
.badges {
    display: flex;
    align-items: center;
    overflow: hidden;
    white-space: nowrap;
}
</style>
