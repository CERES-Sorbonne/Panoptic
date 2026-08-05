<script setup lang="ts">
import { useDataStore } from '@/data/dataStore';
import { Colors, greyColor, Tag } from '@/data/models';
import { computed } from 'vue';
import WithToolTip from '../tooltips/withToolTip.vue';

const data = useDataStore()

const props = defineProps<{
    showDelete?: boolean,
    id?: number,
    name?: string,
    color?: number
}>()

const tag = computed(() => data.tags[props.id])

const color = computed(() => {
    if (props.color >= 0 && props.color <= 12) return Colors[props.color].color
    if (!tag.value) return greyColor.color
    if (tag.value.color < 0 || tag.value.color > 12) return greyColor.color
    return Colors[tag.value.color].color
})

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

// Pastel chip: a washed-out tint of the tag colour, with the text a deep version of the same
// hue so it stays readable instead of fighting the fill.
const background = computed(() => mix(color.value, 0.72))
const textColor = computed(() => mix(color.value, -0.55))

const name = computed(() => {
    if (props.name) return props.name
    if (!tag.value) return 'undefined'
    return tag.value.value
})

</script>


<template>
    <div class="badge tag-badge" :style="{ backgroundColor: background, color: textColor }">

        <span class="m-0 p-0 label">
            <span>{{ name }}</span>
            <!-- trails the label, as on the chips in the tag editor -->
            <span v-if="showDelete" @click.prevent.stop="$emit('delete')" class="bi bi-x tag-x"></span>
        </span>
    </div>
</template>


<style scoped>
.tag-badge {
    margin: 0;
    padding: 0px 6px;
    border-radius: 4px !important;
    /* .badge ships line-height: 1, so the chip's line box places the baseline differently from the
       surrounding text and the label reads a couple of pixels low. Inheriting the text line-height
       makes both line boxes identical, so centring the chip also aligns the baselines. */
    line-height: inherit;
    /* .badge ships 700 weight at .75em, which reads as a different typeface next to the rest
       of the UI: take the surrounding text's size and weight instead. */
    font-size: inherit;
    font-weight: 400;
}

/* The delete glyph is a font icon with taller metrics than the label: left inline it stretches
   the badge's line box and pushes the label off centre. Laying the two out as a flex row takes
   the glyph's metrics out of the line entirely. */
.label {
    display: inline-flex;
    align-items: center;
}

/* inherits the badge's text colour, dimmed, so it never fights the label */
.tag-x {
    margin-left: 3px;
    opacity: 0.55;
    line-height: 1;
}

.tag-x:hover {
    cursor: pointer;
    opacity: 1;
}
</style>