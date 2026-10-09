// What a tree property row shows at rest, as plain functions: shared by the typed inputs (which
// draw it while not editing) and TreeCellView (which only ever draws it), so the read-only row
// and the editor it is swapped for can never disagree on a value.
import { Colors, greyColor, isReadonly, Property, PropertyType, Tag } from '@/data/models'
import { isTag } from '@/utils/utils'

// PropertyIcon's glyph for a type, as a class, for markup that can't afford a component per row.
// `_id` has no glyph (PropertyIcon draws a bold "ID"): empty string.
export function propertyIconClass(type: PropertyType): string {
    switch (type) {
        case PropertyType.string: return 'bi bi-text-left'
        case PropertyType.number: return 'bi bi-123'
        case PropertyType.date: return 'bi bi-calendar-date'
        case PropertyType.path: return 'bi bi-code-slash'
        case PropertyType.image_link: return 'bi bi-card-image'
        case PropertyType.url: return 'bi bi-globe'
        case PropertyType.color: return 'bi bi-palette'
        case PropertyType.checkbox: return 'bi bi-check-square'
        case PropertyType.tag: return 'bi bi-tag-fill'
        case PropertyType.multi_tags: return 'bi bi-tags-fill'
        case PropertyType._folders: return 'bi bi-folder'
        case PropertyType._id: return ''
        case PropertyType._width: return 'bi bi-arrows'
        case PropertyType._height: return 'bi bi-arrows-vertical'
        default: return 'bi bi-hash'
    }
}

// A cell row is one line high, so line breaks can't be shown as line breaks: the value is cut
// on them and each break is drawn back as a ⏎ icon, keeping the real text readable on one line.
export function textLines(value: string | undefined): string[] {
    return (value ?? '').split(/\r?\n/)
}

// "No value" covers more than `undefined` here: a group's value can come in as null, and a
// cluster/undecided card can carry a NaN — none of which is a number to show.
export function numberValue(v: any): number | undefined {
    return typeof v === 'number' && !isNaN(v) ? v : undefined
}

// The fill of a colour row; undefined when unset, grey for an index outside the palette.
export function colorFill(v: any): string | undefined {
    if (v == undefined) return undefined
    const value = Number(v)
    if (isNaN(value) || value < 0 || value >= Colors.length) return greyColor.color
    return Colors[value].color
}

// Icon sits on top of the chip: flip it to white once the fill is dark enough that the
// default grey would disappear into it. Relative luminance, sRGB coefficients.
export function iconColorOn(color: string | undefined): string | undefined {
    if (!color) return undefined
    const hex = color.replace('#', '')
    if (hex.length !== 6) return undefined
    const [r, g, b] = [0, 2, 4].map(i => parseInt(hex.slice(i, i + 2), 16) / 255)
    const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return lum > 0.55 ? '#333' : '#fff'
}

// Badges carry no text separator, so the hover tooltip (and the copy button) spell the list out.
export function tagNames(ids: number[] | undefined, tags: { [id: number]: Tag }): string {
    return (ids ?? []).map(id => tags[id]?.value).filter(Boolean).join(', ')
}

// A row's full value, for its tooltip and copy button, when the row's own text would lose part of
// it: the raw value of an editable text row (TreeTextInput draws its line breaks as icons), the tag
// names of a tag row. Undefined: the text the row shows is the value.
export function cellFullText(property: Property, value: any, tags: { [id: number]: Tag }): string | undefined {
    if (isTag(property.type)) return tagNames(value, tags)
    if (!isReadonly(property) && (property.type == PropertyType.string || property.type == PropertyType.url)) return value
    return undefined
}
