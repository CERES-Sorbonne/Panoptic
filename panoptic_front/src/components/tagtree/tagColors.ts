// A tag chip's colours, out of TagBadge so the scrollers' read-only cells can paint the same chip
// as plain markup instead of mounting a TagBadge per tag.
import { Colors, greyColor, Tag } from '@/data/models'

function rgb(hex: string) {
    const h = hex.replace('#', '')
    return [0, 2, 4].map(i => parseInt(h.slice(i, i + 2), 16))
}

// Blend towards white (amount > 0) or black (amount < 0).
function mix(hex: string, amount: number) {
    const target = amount > 0 ? 255 : 0
    const t = Math.abs(amount)
    const [r, g, b] = rgb(hex).map(c => Math.round(c + (target - c) * t))
    return `rgb(${r}, ${g}, ${b})`
}

// The tag's colour, or `color` when given (0-12); grey when neither names a palette entry.
export function tagColor(tag: Tag | undefined, color?: number): string {
    if (color >= 0 && color <= 12 && Colors[color]) return Colors[color].color
    if (!tag) return greyColor.color
    if (tag.color < 0 || tag.color > 12 || !Colors[tag.color]) return greyColor.color
    return Colors[tag.color].color
}

// Pastel chip: a washed-out tint of the tag colour, with the text a deep version of the same
// hue so it stays readable instead of fighting the fill.
export function tagChipStyle(color: string) {
    return { backgroundColor: mix(color, 0.72), color: mix(color, -0.55) }
}
