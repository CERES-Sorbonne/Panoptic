<script setup lang="ts">
// A grid cell at rest: exactly what GridPropInput draws while nobody edits it (the reading state
// of CellTagInput, CellTextInput, CellUrlInput, CheckboxInput, CellColorInput, RowDateInput,
// RowNumberInput, and the read-only branches), as plain markup. No DBInput, no Dropdown, no
// ContentEditable, no watcher. RowLine swaps it for the real GridPropInput only while the cell
// is being edited.
//
// Keep the markup and the CSS in step with those inputs: the cell is swapped for one of them on
// click, and nothing must move when it is. One deliberate difference: text and tags are capped at
// six lines here (see .capped-text / .capped-tags), the editor shows the whole value, and
// the row grows to it (rows fit their content, see rowHeights.ts).
import { Colors, Property, PropertyType } from '@/data/models'
import { InstanceEntry } from '@/data/stores/instanceStore'
import { useDataStore } from '@/data/stores/dataStore'
import { keyState } from '@/data/composables/keyState'
import { isNumeric, isTag } from '@/utils/utils'
import { formatDate } from '@/components/property_preview/formatDate'
import { tagChipStyle, tagColor } from '@/components/tagtree/tagColors'

const data = useDataStore()

const props = defineProps<{
    instance: InstanceEntry
    property: Property
    minHeight: number
    width: number
}>()

const value = () => props.instance.properties[props.property.id]
const type = () => props.property.type

// CellColorInput's fill: grey for anything that is not a palette index.
function colorOf(v: any) {
    if (v == undefined) return 'white'
    const n = Number(v)
    if (isNaN(n) || n > 12 || !Colors[n]) return 'gray'
    return Colors[n].color
}

// NumberInput shows the value only when it reads as a number.
function numberText(v: any) {
    return !isNaN(Number(v)) ? v : undefined
}

function setValue(v: any) {
    // same dedupe as DBInput.set: an unchanged value is not a write
    if (JSON.stringify(v) === JSON.stringify(value())) return
    data.setPropertyValue(props.property.id, props.instance, v)
}

// CheckboxInput writes unset rather than false.
function onCheck(e: Event) {
    setValue((e.target as HTMLInputElement).checked ? true : undefined)
}

// TextInput's url mode: ctrl-click opens the link, and is not an edit.
function onUrlClick(e: MouseEvent) {
    const v = value()
    if (!keyState.ctrl || !v) return
    e.stopPropagation()
    const url = v.startsWith('http') ? v : 'http://' + v
    window.open(url, '_blank')?.focus()
}
</script>

<template>
    <!-- GridPropInput's root and DBInput slot wrapper -->
    <div>
        <div style="padding: 2px 0px">
            <!-- CellTagInput's button, wrapped as its editor wraps it, capped -->
            <div v-if="isTag(type())" class="btn-class text-wrap capped-tags" :style="{ width: props.width + 'px' }">
                <span v-for="id in (value() ?? [])"><div v-if="data.tags[id]" class="badge tag-badge me-1"
                        :title="data.tags[id].value" :style="tagChipStyle(tagColor(data.tags[id]))"><span
                            class="m-0 p-0 label"><span>{{ data.tags[id].value }}</span></span></div></span>
                <span v-if="!(value() ?? []).length" style="font-size: 14px;" class="text-secondary">{{ $t('none') }}</span>
            </div>

            <!-- CellTextInput / CellUrlInput: the preview while unset, TextInput's box otherwise -->
            <div v-else-if="type() == PropertyType.string || type() == PropertyType.url">
                <div v-if="value() === undefined" class="text-secondary" style="font-size: inherit; cursor: pointer;">
                    {{ $t('none') }}</div>
                <div v-else class="container m-0 p-0 text-box" :class="{ 'grid-url': type() == PropertyType.url }"
                    :style="{ width: props.width > 0 ? props.width + 'px' : '100%', minHeight: (props.minHeight - 6) + 'px' }"
                    @click="type() == PropertyType.url ? onUrlClick($event) : undefined">
                    <div class="h-100 w-100 text" :style="{ width: (props.width - 5) + 'px' }">
                        <div class="capped-text">{{ value() }}</div>
                    </div>
                </div>
            </div>

            <!-- CheckboxInput: toggles in place, no editor -->
            <div v-else-if="type() == PropertyType.checkbox" class="d-flex">
                <div><input class="offset-input" type="checkbox" :checked="value()" @input="onCheck" @click.stop></div>
                <div></div>
            </div>

            <!-- CellColorInput's button -->
            <template v-else-if="type() == PropertyType.color">
                <div v-if="value() !== undefined" :style="{ height: (props.minHeight - 2) + 'px' }" style="cursor: pointer;">
                    <div style="margin: auto; height: calc(100% - 3px); position: relative; top: 0px;"
                        :style="{ width: props.width + 'px', backgroundColor: colorOf(value()) }"></div>
                </div>
                <div v-else class="text-secondary" style="cursor: pointer;" :style="{ width: props.width + 'px' }">
                    {{ $t('none') }}</div>
            </template>

            <!-- RowDateInput's button (DatePreview) -->
            <div v-else-if="type() == PropertyType.date" style="font-size: 14px;">
                <div class="row-preview" style="cursor: pointer; width: 100%;">
                    <span v-if="!formatDate(value())" class="text-secondary">{{ $t('none') }}</span>
                    <span v-else>{{ formatDate(value()) }}</span>
                </div>
            </div>

            <!-- RowNumberInput: NumberPreview while unset, NumberInput's field otherwise. A real
                 field, kept out of focus and tab order, so it draws exactly like the one it stands
                 in for. -->
            <div v-else-if="type() == PropertyType.number">
                <div v-if="value() === undefined" style="font-size: inherit; cursor: pointer; width: 100%;">
                    <div class="text-secondary">{{ $t('none') }}</div>
                </div>
                <div v-else style="line-height: 19px; top: 0px; position: relative;">
                    <div><input class="number-field" type="number" readonly tabindex="-1"
                            style="line-height: inherit; background-color: inherit; width: 100%;"
                            :value="numberText(value())" @mousedown.prevent></div>
                </div>
            </div>

            <div v-else-if="type() == PropertyType._folders" :style="{ height: props.minHeight + 'px' }"
                class="ps-1 overflow-hidden">
                <span v-if="value() != undefined"><div class="badge tag-badge"
                        :title="data.folders[value()]?.name || 'undefined'" :style="tagChipStyle(tagColor(undefined))"><span
                            class="m-0 p-0 label"><span>{{ data.folders[value()]?.name || 'undefined' }}</span></span></div></span>
            </div>

            <!-- read-only values, on one line -->
            <div v-else class="text-truncate" style="padding: 0 2px;" :class="{ num: isNumeric(type()) }">{{ value() }}</div>
        </div>
    </div>
</template>

<style scoped>
/* CellTagInput */
.btn-class {
    overflow: hidden;
    cursor: pointer;
}

/* The cap at rest, six lines (of 1.5em, the body line height): a row grows to its tallest
   cell, and a long note or a hundred tags would otherwise make one row taller than the screen.
   Six lines shows a paragraph or a few rows of tags while keeping several rows in view, and bounds
   how far an unmeasured row can be off its estimate. Text ends on an ellipsis (line breaks
   count as lines). Tags fade out at the cap: the gradient's stops are in px from the top, so
   content shorter than the cap lies wholly in the opaque part and does not fade. */
.capped-text {
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 6;
    line-clamp: 6;
    overflow: hidden;
}

.capped-tags {
    --cap: calc(6 * 1.5em);
    max-height: var(--cap);
    -webkit-mask-image: linear-gradient(to bottom, black calc(var(--cap) - 1em), transparent var(--cap));
    mask-image: linear-gradient(to bottom, black calc(var(--cap) - 1em), transparent var(--cap));
}

/* TagBadge */
.tag-badge {
    margin: 0;
    padding: 0px 6px;
    border-radius: 4px !important;
    line-height: inherit;
    font-size: inherit;
    font-weight: 400;
}

.label {
    display: inline-flex;
    align-items: center;
}

/* TextInput: its box (.container), then ContentEditable's (.contenteditable) */
.text-box {
    border-radius: 5px;
}

.text {
    white-space: break-spaces;
    overflow-wrap: break-word;
    padding-left: 2px;
    padding-right: 2px;
    box-sizing: content-box;
}

/* CheckboxInput */
.offset-input {
    position: relative;
    top: 2px;
}

/* DatePreview */
.row-preview {
    font-size: inherit;
}

/* NumberInput */
.number-field {
    border: none;
    text-align: left;
    -moz-appearance: textfield;
    border-radius: 5px;
}

.number-field::-webkit-inner-spin-button,
.number-field::-webkit-outer-spin-button {
    -webkit-appearance: none;
    margin: 0;
}
</style>

<style>
/* TextInput's url mode: with ctrl held, a hovered link reads as one (GridScroller sets
   .ctrl-held while ctrl is down). Unscoped: a scoped rule can't depend on an ancestor's class. */
.ctrl-held .grid-url:hover {
    cursor: pointer;
    color: blue;
}
</style>
