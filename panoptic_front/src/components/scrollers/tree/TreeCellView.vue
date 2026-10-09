<script setup lang="ts">
// A tree property row at rest: exactly what TreePropertyInput draws while nobody edits it
// (TreeCellFrame + the typed input's reading state), as plain markup. No DBInput, no editor, no
// popup Teleport, no tooltip, no hover source, no watcher: a card shows one of these per
// property, and Image.vue swaps a row for the real editor (TreePropertyInput) only while that
// row is being edited.
//
// Hover is not handled here either: the row carries data attributes and the scroller handles
// pointer events for all rows at once (see cellHover.ts). It only says, through `pointed`, which
// row gets the filter/copy buttons.
//
// Keep the markup and the CSS in step with TreeCellFrame and the Tree*Input components: the row
// is swapped for one of them on click, and nothing must move when it is.
import TreeRowActions from './TreeRowActions.vue'
import { deletedID, isReadonly, Property, PropertyType } from '@/data/models'
import { InstanceEntry } from '@/data/stores/instanceStore'
import { useDataStore } from '@/data/stores/dataStore'
import { keyState } from '@/data/composables/keyState'
import { isNumeric, isTag } from '@/utils/utils'
import { formatDate } from '@/components/property_preview/formatDate'
import { tagChipStyle, tagColor } from '@/components/tagtree/tagColors'
import { cellAttrs } from '../cellHover'
import { cellFullText, colorFill, iconColorOn, numberValue, propertyIconClass, textLines } from './cellDisplay'

const data = useDataStore()

const props = defineProps<{
    instance: InstanceEntry
    property: Property
    groupId: number
    // the pointer is on this row: mount its filter/copy buttons
    pointed?: boolean
}>()

// Asks the card to swap this row for its editor.
const emits = defineEmits(['open'])

// Which reading state this row reproduces: the typed input TreePropertyInput would mount, or
// 'plain' for TreeValueRow (computed / non-editable properties, and types with no input yet).
type Kind = 'text' | 'number' | 'checkbox' | 'tags' | 'color' | 'date' | 'plain'

// Plain functions rather than computeds: the template reads each of them once per render, and a
// card holds one row per property — a computed per row and per value is what this replaces.
function kind(): Kind {
    const type = props.property.type
    if (isReadonly(props.property)) return 'plain'
    if (type == PropertyType.string || type == PropertyType.url) return 'text'
    if (type == PropertyType.number) return 'number'
    if (type == PropertyType.checkbox) return 'checkbox'
    if (isTag(type)) return 'tags'
    if (type == PropertyType.color) return 'color'
    if (type == PropertyType.date) return 'date'
    return 'plain'
}

const value = () => props.instance.properties[props.property.id]
const tags = () => (value() ?? []) as number[]

// The editable rows sit in TreePropertyInput's save-status wrapper; the readonly ones never had it.
const status = () => props.instance.propertyStatus?.[props.property.id] ?? 'confirmed'

function isEmpty(k: Kind) {
    const v = value()
    switch (k) {
        case 'text': return !v
        case 'number': return numberValue(v) === undefined
        case 'checkbox': return false
        case 'tags': return !tags().length
        case 'color': return colorFill(v) === undefined
        case 'date': return !v
        default: return isTag(props.property.type) ? !tags().length : v === undefined || v === ''
    }
}

// The row's full value, for the copy button (and, through the scroller, the tooltip): the raw
// text for an editable text row (its line breaks are drawn as icons), the tag names for tags,
// otherwise the text the row shows.
function copyText() {
    return cellFullText(props.property, value(), data.tags)
        ?? (rootElem?.querySelector('.value-zone') as HTMLElement)?.innerText.trim()
}

let rootElem: HTMLElement = null
const setRoot = (el: any) => { rootElem = el }

function setValue(v: any) {
    // same dedupe as DBInput.set: an unchanged value is not a write
    if (JSON.stringify(v) === JSON.stringify(value())) return
    data.setPropertyValue(props.property.id, props.instance, v)
}

// Same click as the typed inputs: ctrl/cmd-click on a url opens it rather than editing it, a
// checkbox toggles in place (unset rather than false, so unchecked reads as "no value"), and
// everything else opens the editor. Readonly rows do nothing.
function onClick() {
    const k = kind()
    if (k == 'plain') return
    if (k == 'checkbox') return setValue(value() ? undefined : true)
    const v = value()
    if (props.property.type == PropertyType.url && v && (keyState.ctrl || keyState.cmd)) {
        const url = v.startsWith('http') ? v : 'http://' + v
        window.open(url, '_blank')?.focus()
        return
    }
    emits('open')
}

function key() {
    return { instanceId: props.instance.id, groupId: props.groupId, propertyId: props.property.id }
}
</script>

<template>
    <!-- A deleted instance shows its readonly rows only, as TreePropertyInput did (no DBInput). -->
    <div v-if="isReadonly(props.property) || props.instance.id != deletedID"
        :class="{ 'value-unconfirmed': !isReadonly(props.property) && status() !== 'confirmed' }"
        :title="isReadonly(props.property) ? undefined : (status() === 'pending' ? 'Saving…' : (status() === 'error' ? 'Failed to save' : undefined))">
        <div class="tree-cell" :ref="setRoot" v-bind="cellAttrs(key())" @click="onClick">
            <!-- full-bleed colour fill, under the icon and the value -->
            <div v-if="kind() == 'color' && colorFill(value())" class="chip"
                :style="{ backgroundColor: colorFill(value()) }" />
            <!-- no icon on a checkbox row: the box itself is what the icon would have shown -->
            <div v-if="kind() != 'checkbox'" class="icon-zone"
                :style="kind() == 'color' && colorFill(value()) ? { color: iconColorOn(colorFill(value())) } : undefined">
                <span><b v-if="props.property.type == PropertyType._id" style="padding-left: 2px;">ID</b><i v-else
                        :class="propertyIconClass(props.property.type)" /></span>
            </div>
            <!-- stands in for the wTT trigger span the frame wraps its value zone in -->
            <span class="value-wrap">
                <div class="value-zone">
                    <span v-if="kind() == 'text' && value()" class="value"
                        :class="{ url: props.property.type == PropertyType.url }">
                        <template v-for="(line, i) in textLines(value())" :key="i"><i v-if="i > 0"
                                class="bi bi-arrow-return-left return-icon" />{{ line }}</template>
                    </span>

                    <span v-else-if="kind() == 'number' && !isEmpty('number')" class="value num">{{ value() }}</span>

                    <template v-else-if="kind() == 'checkbox'"><input class="box" type="checkbox"
                            :checked="!!value()" @click.stop="onClick" /><span class="label2">{{
                            props.property.name }}</span></template>

                    <div v-else-if="kind() == 'tags' || (kind() == 'plain' && isTag(props.property.type))"
                        class="badges">
                        <div v-for="id in tags()" :key="id" class="badge tag-badge me-1" title=""
                            :style="tagChipStyle(tagColor(data.tags[id]))">
                            <span class="m-0 p-0 label"><span>{{ data.tags[id]?.value ?? 'undefined' }}</span></span>
                        </div>
                    </div>

                    <!-- DatePreview's markup -->
                    <div v-else-if="kind() == 'date' && value()" class="value">
                        <span v-if="!formatDate(value())" class="text-secondary">{{ $t('none') }}</span>
                        <span v-else>{{ formatDate(value()) }}</span>
                    </div>

                    <template v-else-if="kind() == 'plain'">
                        <div v-if="props.property.type == PropertyType._folders && value() !== undefined"
                            class="badge tag-badge" title="" :style="tagChipStyle(tagColor(undefined))">
                            <span class="m-0 p-0 label"><span>{{ data.folders[value()]?.name || 'undefined' }}</span></span>
                        </div>
                        <span v-else-if="value() !== undefined && value() !== ''" class="value"
                            :class="{ num: isNumeric(props.property.type) }">{{ value() }}</span>
                    </template>

                    <!-- same "Vide..." the property previews show -->
                    <span v-if="isEmpty(kind())" class="empty">{{ $t('none') }}</span>
                </div>
            </span>
            <TreeRowActions v-if="props.pointed && !isEmpty(kind())" :type="props.property.type"
                :filter="{ propertyId: props.property.id, value: value() }" :text="copyText" />
        </div>
    </div>
</template>

<style scoped>
/* ── TreePropertyInput ── */
.value-unconfirmed {
    opacity: 0.45;
    background-color: var(--light-grey);
    transition: opacity 0.15s ease, background-color 0.15s ease;
}

/* ── TreeCellFrame ── (see there for the reasons behind each rule) */
.tree-cell {
    display: flex;
    align-items: center;
    box-sizing: border-box;
    width: 100%;
    height: 26px;
    padding-left: 4px;
    padding-right: 1px;
    background-color: transparent;
    transition: background-color 0.2s;
    position: relative;
    z-index: 5;
    cursor: pointer;
    font-size: 14px;
    line-height: 18px;
}

.tree-cell::after {
    content: '';
    position: absolute;
    inset: 0;
    box-shadow: inset 0 0 0 1px transparent;
    transition: box-shadow 0.2s;
    pointer-events: none;
    z-index: 1;
}

.tree-cell:hover {
    background-color: white;
}

.tree-cell:hover::after {
    box-shadow: inset 0 0 0 1px var(--border-color);
}

/* a checkbox row keeps its box focusable */
.tree-cell:focus-within {
    background-color: white;
}

.tree-cell:focus-within::after {
    box-shadow: inset 0 0 0 1px var(--cell-blue);
}

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

/* wTT's trigger span (.wtt-trigger.text-nowrap.m-0.p-0) plus the inline flex sizing the frame
   gives it */
.value-wrap {
    display: inline-flex;
    align-items: center;
    flex: 1 1 auto;
    min-width: 0;
    white-space: nowrap;
    margin: 0;
    padding: 0;
}

.value-zone {
    position: relative;
    flex: 1 1 auto;
    min-width: 0;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
}

/* TreeRowActions' root */
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

.tree-cell:hover:not(:focus-within) .row-actions {
    display: inline-flex;
}

.empty {
    color: var(--text-secondary, #6c757d);
}

/* ── the typed inputs' reading state ── */
.value {
    display: block;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
}

/* TreeTextInput */
.return-icon {
    color: var(--grey-text);
    font-size: 0.85em;
    margin: 0 3px;
    vertical-align: baseline;
}

.url {
    color: var(--blue);
}

/* TreeTagInput / TreeValueRow */
.badges {
    display: flex;
    align-items: center;
    overflow: hidden;
    white-space: nowrap;
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

/* TreeColorInput */
.chip {
    position: absolute;
    inset: 0;
    box-shadow: inset 1px 0 0 var(--border-color), inset -1px 0 0 var(--border-color);
}

/* TreeCheckboxInput */
.box {
    vertical-align: middle;
    margin: 0;
    cursor: pointer;
}

.label2 {
    margin-left: 3px;
    vertical-align: middle;
}
</style>
