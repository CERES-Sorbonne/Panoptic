<script setup lang="ts">
import Zoomable from '@/components/Zoomable.vue';
import CenteredImage from '@/components/images/CenteredImage.vue';
import CheckboxPropInput from '@/components/inputs/CheckboxPropInput.vue';
import ColorPropInput from '@/components/inputs/ColorPropInput.vue';
import DatePropInput from '@/components/inputs/DatePropInput.vue';
import SelectCircle from '@/components/inputs/SelectCircle.vue';
import TextPropInput from '@/components/inputs/TextPropInput.vue';
import TagPropInputDropdown from '@/components/tags/TagPropInputDropdown.vue';
import TagBadge from '@/components/tagtree/TagBadge.vue';
import { Group } from '@/core/GroupManager';
import { ModalId, PileRowLine, Property, PropertyType, RowLine } from '@/data/models';
import { usePanopticStore } from '@/data/panopticStore';
import { useProjectStore } from '@/data/projectStore';
import { isTag } from '@/utils/utils';
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue';

const panoptic = usePanopticStore()
const project = useProjectStore()

const props = defineProps({
    item: Object,
    properties: Array<Property>,
    showImage: Boolean,
    selected: Boolean,
    missingWidth: Number,
    // expandImage: Boolean
})
const emits = defineEmits({
    'resizeHeight': Number,
    'toggle:image': Object,
})

const inputElems = reactive([])
const hover = ref(false)



const tab = computed(() => project.getTab())
const image = computed(() => {
    if (props.item.type == 'pile') {
        return (props.item as PileRowLine).data.images[0]
    }
    return (props.item as RowLine).data
})

const pile = computed(() => {
    if (props.item.type == 'pile') {
        return props.item.data as Group
    }
    return undefined
})

const rowHeight = computed(() => {
    let max = 0
    for (let k in sizes) {
        if (sizes[k] > max) {
            max = sizes[k]
        }
    }
    if (props.showImage) {
        return Math.max(Math.max(max, imageSize.value.h) + 4, 30)
    }
    return max + 4
})

const propMinRowHeight = computed(() => {
    const res: { [propId: number]: number } = {}
    for (let prop of props.properties) {
        let max = 0
        for (let k in sizes) {
            if (sizes[k] > max && Number(prop.id) != Number(k)) {
                max = sizes[k]
            }
        }
        if (props.showImage) {
            // max = Math.max(max, tab.value.data.imageSize)
            max = Math.max(max, imageSize.value.h)
        }
        max = Math.max(max, props.showImage ? 26 : 24)
        res[prop.id] = max
    }
    return res
})

const sizes: { [key: string | number]: number } = reactive({})

const propWidth = computed(() => {
    const res = {} as { [propId: number]: number }
    props.properties.forEach(p => res[p.id] == tab.value.propertyOptions[p.id].size)
    return res
})


const imageSize = computed(() => {
    let imgRatio = image.value.width / image.value.height
    let divRatio = 1

    if (divRatio > imgRatio) {
        return { w: tab.value.imageSize * imgRatio, h: tab.value.imageSize }
    }
    return { w: tab.value.imageSize, h: tab.value.imageSize / imgRatio }

})

const inputWidth = computed(() => {
    const res = {} as { [propId: string]: number }
    props.properties.forEach(p => {
        res[p.id] = tab.value.propertyOptions[p.id].size - 7
        if (p.id == props.properties[props.properties.length - 1].id) {
            if (props.missingWidth > 0) res[p.id] += props.missingWidth

            res[p.id] -= 15 // remove scrolling bar width
        }
    })
    return res
})

// const totalPropWidth = computed(() => {
//     return Object.values(propWidth.value).reduce((a,b) => a+b, 0)
// })

const classes = computed(() => {
    const res = ['header-cell']
    if (props.item.index == 0) {
        res.push('top-border')
    }
    return res
})


function focusInput(index: number) {
    console.log(inputElems[index])
    inputElems[index].focus()
    // inputElems[index].getInput().focus()
    // inputElems[index].inputElem
}

function log(value: any) {
    console.log(Object.keys(value))
}

let _emitResize = false
function emitResizeOnce() {
    if (_emitResize) return
    _emitResize = true
    nextTick(() => {
        emits('resizeHeight', rowHeight.value)
        _emitResize = false
    })
}

function showModal() {
    // console.log(props.item.iterator)
    panoptic.showModal(ModalId.IMAGE, props.item.iterator)
}



onMounted(emitResizeOnce)
// watch(props, emitResizeOnce)
watch(rowHeight, emitResizeOnce)

</script>


<template>
    <div class="container" :style="{ height: props.item.size + 'px' }">
        <div class="left-border" :style="{ height: props.item.size + 'px' }"></div>
        <div v-if="showImage" :class="classes" :style="{
            width: (tab.imageSize) + 'px', position: 'relative', height: rowHeight + 'px', cursor: 'pointer',
        }" class="p-0 m-0" @mouseenter="hover = true" @mouseleave="hover = false" @click="showModal">
            <Zoomable :image="image">
                <CenteredImage :image="image" :width="tab.imageSize - 1" :height="rowHeight - 2" />
                <div v-if="hover || props.selected" class="h-100 box-shadow" :style="{ width: tab.imageSize + 'px' }"
                    style="position: absolute; top:0; left:0; right: 0px; bottom: 0px;"></div>
                <SelectCircle v-if="hover || props.selected" :model-value="props.selected"
                    @update:model-value="v => emits('toggle:image', { groupId: item.groupId, imageIndex: item.index })"
                    class="select" :light-mode="true" />
                <div class="image-count" v-if="pile?.images.length > 1">{{ pile.images.length }}</div>
            </Zoomable>
        </div>

        <!-- <div class=""> -->
        <div v-for="property, index in props.properties" :class="classes"
            :style="{ width: inputWidth[property.id] + 7 + 'px' }">
            <!-- {{ rowHeight }} -->
            <!-- <template v-if="image.properties[property.id] != undefined"> -->
            <TextPropInput v-if="property.type == PropertyType.string" :min-height="props.item.size" ref="inputElems"
                @update:height="h => sizes[property.id] = (h)" :image="image" :property="property"
                :width="inputWidth[property.id]" />
            <TextPropInput v-else-if="property.type == PropertyType.url" :min-height="props.item.size" :no-nl="true"
                ref="inputElems" @update:height="h => sizes[property.id] = (h)" :image="image" :property="property"
                :url-mode="true" :width="inputWidth[property.id]" />
            <TextPropInput v-else-if="property.type == PropertyType.path" :min-height="props.item.size" :no-nl="true"
                ref="inputElems" @update:height="h => sizes[property.id] = (h)" :image="image" :property="property"
                :url-mode="false" :width="inputWidth[property.id]" />
            <TagPropInputDropdown v-else-if="isTag(property.type)" :property="property" :image="image" :can-create="true"
                :can-customize="true" :can-link="true" :can-delete="true" :auto-focus="true" :no-wrap="false"
                :min-height="propMinRowHeight[property.id]" :width="inputWidth[property.id]" :teleport="true"
                @update:height="h => sizes[property.id] = h" />
            <CheckboxPropInput v-else-if="property.type == PropertyType.checkbox"
                :min-height="propMinRowHeight[property.id]" ref="inputElems" @update:height="h => sizes[property.id] = (h)"
                :image="image" :property="property" :width="inputWidth[property.id]" />
            <ColorPropInput v-else-if="property.type == PropertyType.color" :min-height="propMinRowHeight[property.id]"
                ref="inputElems" @update:height="h => sizes[property.id] = (h)" :image="image" :property="property"
                :width="inputWidth[property.id]" />

            <TextPropInput v-else-if="property.type == PropertyType.number" :min-height="props.item.size" ref="inputElems"
                @update:height="h => sizes[property.id] = (h)" :image="image" :property="property"
                :width="inputWidth[property.id]" />

            <DatePropInput v-else-if="property.type == PropertyType.date" :min-height="propMinRowHeight[property.id]"
                ref="inputElems" @update:height="h => sizes[property.id] = (h)" :image="image" :property="property"
                :width="inputWidth[property.id]" />
            <div v-else-if="property.type == PropertyType._ahash" :style="{ height: propMinRowHeight[property.id] + 'px' }"
                class="ps-1 overflow-hidden">
                {{ image.properties[property.id]?.value }}
            </div>
            <div v-else-if="property.type == PropertyType._folders"
                :style="{ height: propMinRowHeight[property.id] + 'px' }" class="ps-1 overflow-hidden">
                <span v-if="image.properties[property.id]?.value != undefined">
                    <TagBadge :tag="project.data.folders[image.properties[property.id]?.value].name" :color="-1" />
                </span>
            </div>
            <div v-else :style="{ height: (propMinRowHeight[property.id]) + 'px' }" class="ps-1 overflow-hidden">
                {{ image.properties[property.id]?.value }}
            </div>
            <!-- </template> -->
            <!-- <template v-else>None</template> -->
        </div>
        <!-- </div> -->
    </div>
</template>

<style scoped>
.image-count {
    position: absolute;
    top: 0;
    right: 0;
    padding: 0px 4px;
    background-color: var(--border-color);
    color: var(--grey-text);
    font-size: 10px;
    line-height: 15px;
    margin: 2px;
    border-radius: 5px;
    z-index: 100;
}

.select {
    position: absolute;
    top: 0;
    left: 5px;
}

.left-border {
    border-left: 1px solid var(--border-color);
    display: inline-block;
    width: 1px;
    /* height: 100%; */
}

.container {
    margin: 0;
    padding: 0;
    display: table;
    table-layout: fixed;
}

.header-cell {
    vertical-align: top;
    border-left: none;
    border-right: 1px solid var(--border-color);
    border-bottom: 1px solid var(--border-color);
    /* overflow: hidden; */
    /* resize: horizontal; */
    padding-top: 3px;
    padding-left: 3px;
    margin: 0;
    display: inline-block;
    /* box-sizing: content-box; */
    /* cursor:text; */
    /* border-top: 1px solid red; */
}

.prop-input {
    margin: 3px;
}

.top-border {
    border-top: none;
}


.box-shadow {
    position: relative;
}

.box-shadow::after {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 1px;
    height: 100%;
    -webkit-box-shadow: inset 0px 50px 30px -30px rgba(0, 0, 0, 0.5);
    -moz-box-shadow: inset 0px 50px 30px -30px rgba(0, 0, 0, 0.5);
    box-shadow: inset 0px 50px 30px -30px rgba(0, 0, 0, 0.5);
    overflow: hidden;
}
</style>