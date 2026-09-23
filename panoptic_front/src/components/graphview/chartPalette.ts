/**
 * Colours for the graph view.
 *
 * The 12 categorical slots are assigned in FIXED order (never cycled, never by rank) so a
 * series keeps its colour when the data around it changes. The order itself is the
 * colour-blind-safety mechanism: it was checked with the dataviz palette validator against
 * this app's white chart surface (light mode, surface #ffffff) and passes every hard gate —
 * lightness band, chroma floor, adjacent-pair CVD separation (worst ΔE 9.1, protan) and
 * adjacent-pair normal-vision separation (worst ΔE 19.6). Four slots sit below 3:1 contrast
 * on white, which is only legal with relief: the always-present legend, the hover crosshair
 * readout and the tooltip's numbers all carry identity without relying on hue.
 *
 * Past 12 distinct values the tail folds into one grey "Other" series (see chartModel.ts)
 * instead of inventing new hues.
 *
 * Tag values are the exception: when every series is a tag that carries its own colour, we
 * use those instead, so a value reads the same here as in the map and tree views.
 */
export const CHART_PALETTE = [
    '#2a78d6', // blue
    '#eb6834', // orange
    '#1baf7a', // aqua
    '#eda100', // yellow
    '#e87ba4', // magenta
    '#008300', // green
    '#4a3aa7', // violet
    '#e34948', // red
    '#0f9bb0', // cyan
    '#a85f1a', // ochre
    '#7cb518', // lime
    '#b04ac2', // purple
]

/** Neutral for the folded "Other" series — it is a bucket, not an entity. */
export const OTHER_COLOR = '#898781'

/** Chart chrome, kept recessive and in the app's cool grey family. */
export const CHART_CHROME = {
    surface: '#ffffff',
    grid: '#e9edf1',
    axis: '#c3cfd9',
    label: '#8a949e',
    ink: '#293845',
    /** Wash marking the selected x-range. */
    selection: 'rgba(22, 120, 194, 0.12)',
    selectionLine: 'rgba(22, 120, 194, 0.55)',
}

export function paletteColor(index: number): string {
    return CHART_PALETTE[index % CHART_PALETTE.length]
}
