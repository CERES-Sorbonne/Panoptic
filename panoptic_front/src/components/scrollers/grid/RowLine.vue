<script setup lang="ts">
import Zoomable from '@/components/Zoomable.vue';
import CenteredImage from '@/components/images/CenteredImage.vue';
import SelectCircle from '@/components/inputs/SelectCircle.vue';
import { Group, GroupManager } from '@/core/GroupManager';
import { ModalId, PileRowLine, Property, RowLine } from '@/data/models';
import { usePanopticStore } from '@/data/panopticStore';
import { useProjectStore } from '@/data/projectStore';
import { useDataStore } from '@/data/dataStore';
import { useColumnStore } from '@/data/columnStore';
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue';
import GridPropInput from './GridPropInput.vue';
import { TabManager } from '@/core/TabManager';

const panoptic = usePanopticStore()
const project  = useProjectStore()
const store    = useDataStore()
const columnStore = useColumnStore()

const props = defineProps<{
    tab: TabManager,
    manager: GroupManager,
    item: any,
    properties: Property[],
    showImage: boolean,
    selected?: boolean,
    missingWidth: number,
    // expandImage: boolean
}>()
const emits = defineEmits({
    'resizeHeight': Number,
    'toggle:image': Object,
})

const inputElems = ref([])
const hover = ref(false)



const tab = computed(() => props.tab.state)
const rawImage = computed(() => {
    if (props.item.type == 'pile') {
        const group = (props.item as PileRowLine).data as Group
        const instanceId = columnStore.instanceIds()[group.slots[0]]
        return store.instances[instanceId] ?? { id: instanceId, imageUrl: '', properties: {} }
    }
    return (props.item as RowLine).data
})

// Use the reactive instance from the store so property values populated by
// InstanceData (via register) are reflected here without an extra fetch.
const image = computed(() =>
    (store.instances[rawImage.value.id] ?? rawImage.value) as typeof rawImage.value
)

const pile = computed(() => {
    if (props.item.type == 'pile') {
        return props.item.data as Group
    }
    return undefined
})

const imageHeight = computed(() => {
    if (props.showImage) {
        return Math.max(imageSize.value.h + 4, 30)
    }
    return 0
})

const rowHeight = computed(() => {
    let max = 0
    for (let k in sizes) {
        if (sizes[k] > max) {
            max = sizes[k]
        }
    }
    if (props.showImage) {
        return Math.max(max, imageHeight.value)
    }
    return max + 4
})

// const imageIsTop = computed(() => objValues(sizes).some(h => h > imageHeight.value))

const propMinRowHeight = computed(() => {
    // console.log('update min row height')
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
            max = Math.max(max, imageSize.value.h+4)
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
    const imgRatio = 1
    if (1 > imgRatio) {
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
    console.log(inputElems.value[index])
    inputElems.value[index].focus()
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
    let iterator
    if (props.item.type === 'pile') {
        const sha1Group = (props.item as PileRowLine).data as Group
        iterator = props.manager.getImageIterator(sha1Group.parent.id, sha1Group.parentIdx)
    } else {
        const rowItem = props.item as RowLine
        iterator = props.manager.getImageIterator(rowItem.groupId, rowItem.index)
    }
    panoptic.showModal(ModalId.IMAGE, iterator)
}


onMounted(emitResizeOnce)
// watch(props, emitResizeOnce)
watch(rowHeight, emitResizeOnce)
watch(() => props.properties, () => {
    console.log('cleanup')
    const valid = new Set(props.properties.map(p => p.id))
    Object.keys(sizes).filter(k => !valid.has(Number(k))).forEach(k => delete sizes[k])
})

</script>


<template>
    <div class="d-flex" :style="{ height: props.item.size + 'px' }">
        <div class="left-border" :style="{ height: props.item.size + 'px' }"></div>
        <div v-if="showImage" :class="classes" :style="{
            width: (tab.imageSize) + 'px', position: 'relative', height: rowHeight + 'px', cursor: 'pointer',
        }" class="p-0 m-0" @mouseenter="hover = true" @mouseleave="hover = false" @click="showModal">
            <Zoomable :image="image">
                <CenteredImage :instance-id="image.id" :width="tab.imageSize - 1" :height="rowHeight - 2" />
                <div v-if="hover || props.selected" class="h-100 box-shadow" :style="{ width: tab.imageSize + 'px' }"
                    style="position: absolute; top:0; left:0; right: 0px; bottom: 0px;"></div>
                <SelectCircle v-if="hover || props.selected" :model-value="props.selected"
                    @update:model-value="v => emits('toggle:image', { groupId: item.groupId, imageIndex: item.index })"
                    class="select" :light-mode="true" />
                <div class="image-count" v-if="pile?.slots.length > 1">{{ pile.slots.length }}</div>
            </Zoomable>
        </div>

        <div v-for="property, index in props.properties" class="container22 overflow-hidden"
            :style="{ width: inputWidth[property.id] + 7 + 'px' }"
            style="height: 100%; padding: 0px 3px; font-size: 14px;" @click="focusInput(index)">
            <GridPropInput :instance="image" :property="property" :min-height="propMinRowHeight[property.id]"
                :width="inputWidth[property.id]" @update:height="h => sizes[property.id] = h" ref="inputElems"
                @click.stop="" />
        </div>
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

.container22 {
    border-right: 1px solid var(--border-color);
    border-bottom: 1px solid var(--border-color);
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