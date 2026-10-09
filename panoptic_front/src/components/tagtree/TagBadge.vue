<script setup lang="ts">
import { useDataStore } from '@/data/stores/dataStore';
import { computed } from 'vue';
import { tagChipStyle, tagColor } from './tagColors';

const data = useDataStore()

const props = defineProps<{
    showDelete?: boolean,
    id?: number,
    name?: string,
    color?: number
}>()

const tag = computed(() => data.tags[props.id])

const chip = computed(() => tagChipStyle(tagColor(tag.value, props.color)))

const name = computed(() => {
    if (props.name) return props.name
    if (!tag.value) return 'undefined'
    return tag.value.value
})

</script>


<template>
    <div class="badge tag-badge" :title="name" :style="chip">

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