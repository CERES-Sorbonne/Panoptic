<script setup lang="ts">
// Color property row of a tree cell: a colour chip in the frame, the palette in a popup.
import { computed, ref } from 'vue'
import TreeCellFrame from './TreeCellFrame.vue'
import Dropdown from '@/components/dropdowns/Dropdown.vue'
import { Colors, greyColor, PropertyType } from '@/data/models'

const props = defineProps<{
    modelValue?: number
}>()

const emits = defineEmits(['update:modelValue', 'focus', 'blur', 'tab'])

const dropdownElem = ref(null)
const isOpen = ref(false)

const color = computed(() => {
    if (props.modelValue == undefined) return undefined
    const value = Number(props.modelValue)
    if (isNaN(value) || value < 0 || value >= Colors.length) return greyColor.color
    return Colors[value].color
})

// Icon sits on top of the chip: flip it to white once the fill is dark enough that the
// default grey would disappear into it. Relative luminance, sRGB coefficients.
const iconColor = computed(() => {
    if (!color.value) return undefined
    const hex = color.value.replace('#', '')
    if (hex.length !== 6) return undefined
    const [r, g, b] = [0, 2, 4].map(i => parseInt(hex.slice(i, i + 2), 16) / 255)
    const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return lum > 0.55 ? '#333' : '#fff'
})

function focus() {
    dropdownElem.value?.show()
}

function set(value, hide) {
    emits('update:modelValue', value)
    hide()
}
</script>

<template>
    <Dropdown ref="dropdownElem" :offset="-26" :teleport="true" placement="bottom-start"
        @show="isOpen = true; emits('focus')" @hide="isOpen = false; emits('blur')">
        <template #button>
            <TreeCellFrame :type="PropertyType.color" :active="isOpen" :empty="color === undefined"
                :icon-color="iconColor">
                <template #background>
                    <div v-if="color" class="chip" :style="{ backgroundColor: color }" />
                </template>
            </TreeCellFrame>
        </template>
        <template #popup="{ hide }">
            <div class="palette p-1">
                <div v-for="c, index in Colors" :key="c.name" class="option" @click="set(index, hide)">
                    <div class="swatch" :style="{ backgroundColor: c.color }" />
                    <span class="name">{{ c.name }}</span>
                </div>
                <div class="hr m-1" />
                <div class="option" @click="set(undefined, hide)">
                    <div class="swatch" style="background-color: #ffffff" />
                    <span class="name">{{ $t('none') }}</span>
                </div>
            </div>
        </template>
    </Dropdown>
</template>

<style scoped>
/* floating-vue's trigger wrapper is inline-block: its line box adds descender space under the
   row, which read as a margin the other property rows don't have */
:deep(.v-popper) {
    display: block;
}

/* Edge to edge, icon column included: the frame's border is drawn on TreeCellFrame's ::after
   overlay, which paints above this, so no inset is needed to keep it visible. */
.chip {
    position: absolute;
    inset: 0;
    /* The row sits above the card's edge ring (z-index 5 vs 4), so a full-bleed fill would
       hide it. Redraw those two pixel columns in the border colour instead of insetting the
       fill, which would show as a white gap. */
    box-shadow: inset 1px 0 0 var(--border-color), inset -1px 0 0 var(--border-color);
}

.palette {
    min-width: 120px;
}

.option {
    display: flex;
    align-items: center;
    padding: 3px 5px;
    margin: 0 3px;
    border-radius: 5px;
    cursor: pointer;
}

.option:hover {
    background-color: var(--light-grey);
}

.swatch {
    width: 20px;
    height: 20px;
    border-radius: 15%;
    border: 1px solid var(--border-color);
    margin-right: 5px;
}

.name {
    text-transform: capitalize;
    line-height: 20px;
    color: var(--text-color);
    font-size: 13px;
}
</style>
