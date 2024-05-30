<script setup lang="ts">
// import RecycleScroller from '@/components/Scroller/src/components/RecycleScroller.vue';
import { ShallowReactive, computed, nextTick, onMounted, onUnmounted, reactive, ref, shallowRef, triggerRef, watch } from 'vue';
import TableHeader from './TableHeader.vue';
import { keyState } from '@/data/keyState';
import { Group, GroupManager, GroupType, ImageIterator, ROOT_ID } from '@/core/GroupManager';
import { Property, GroupLine, RowLine, PileRowLine, ScrollerLine, ModalId } from '@/data/models';
import { useProjectStore } from '@/data/projectStore';
import GridScrollerLine from './GridScrollerLine.vue';
import {RecycleScroller} from 'vue-virtual-scroller';
import { usePanopticStore } from '@/data/panopticStore';

const project = useProjectStore()
const panoptic = usePanopticStore()

const props = defineProps({
    manager: GroupManager,
    height: Number,
    width: Number,
    selectedProperties: Array<Property>,
    showImages: Boolean,
    hideIfModal: Boolean
})

defineExpose({
    // scrollTo,
    computeLines,
    clear
})

const hearderHeight = ref(60)
const rowLines = ref([])
const lineSizes: { [id: string]: number } = {}
const scroller = ref(null)
const currentGroup = reactive({} as Group)
const resizeEvent = shallowRef(null)

const totalPropWidth = computed(() => {
    const options = project.getTab().propertyOptions
    let propSum = props.selectedProperties.map(p => options[p.id].size).reduce((a, b) => a + b, 0)
    if (props.showImages) {
        propSum += project.getTab().imageSize
    }
    return propSum
})

const scrollerWidth = computed(() => Math.max(totalPropWidth.value, props.width))

const missingWidth = computed(() => props.width - totalPropWidth.value)

const scrollerHeight = computed(() => props.height - hearderHeight.value)

const scrollerStyle = computed(() => ({
    height: scrollerHeight.value + 'px',
    width: scrollerWidth.value + 'px',
    // overflowX: 'hidden'
}))

const hideFromModal = computed(() => props.hideIfModal && panoptic.openModalId == ModalId.IMAGE)

let dataLines = []
let lineCenter = 0
function computeLines() {
    console.time('Table compute lines')
    const lines = []

    let lastGroupId = undefined
    let current = props.manager.getImageIterator(undefined, undefined, { ignoreClosed: true })
    // lines.push({ id: '__filler__', type: 'fillter', size: 0, index: lines.length })
    while (current) {
        const group = current.group
        if (lastGroupId != group.id && group.id != ROOT_ID) {
            lines.push(computeGroupLine(group))
            lastGroupId = group.id
        }
        if (!group.view.closed && group.images.length) {
            const images = current.images
            if (group.subGroupType != GroupType.Sha1) {
                lines.push(computeImageLine(current, group.id, current.imageIdx))
            } else {
                // lines.push(computePileLine(group.children[current.imageIdx]))
                lines.push(computePileLine(current))
            }
        }
        current = current.nextImages()
    }
    lines.push({ id: '__filler__', type: 'fillter', size: 300, index: lines.length })

    dataLines = lines
    setLines(lines, oldScroll)
    scroller.value.updateVisibleItems(true)
    console.timeEnd('Table compute lines')
}

function setLines(lines: ScrollerLine[], center: number) {
    const start = Math.max(center - props.height * 2, 0)
    const end = Math.max(center + props.height * 3, props.height * 3)
    console.log('set lines', start, center, end)
    let lineSelection = []
    let acc = 0
    let startOffset = undefined
    let endOffset = 0
    for(const line of lines) {
        if(acc + line.size > start && (acc < end || lineSelection.length < 100)) {
            if(startOffset === undefined) {
                startOffset = acc
            }
            lineSelection.push(line)
        }
        else if(acc >= end) {
            endOffset += line.size
        }
        acc += line.size
    }
    lineSelection = [
        { id: '__pre__', type: 'fillter', size: startOffset, index: lines.length },
        ...lineSelection,
        { id: '__post__', type: 'fillter', size: endOffset, index: lines.length }
    ]
    rowLines.value = lineSelection
    lineCenter = center
    scroller.value.scrollToPosition(center)
}

function computeGroupLine(group: Group) {
    // console.log(group)
    const res: GroupLine = {
        id: group.id,
        data: group,
        type: 'group',
        size: 35,
        nbClusters: 10,
        groupId: group.id
    }
    return res
}

function computeImageLine(it: ImageIterator, groupId: string, imageIndex) {
    const image = it.image
    const res: RowLine = {
        id: groupId + '-img:' + String(image.id),
        data: image,
        type: 'image',
        size: lineSizes[image.id] ?? (project.getTab().imageSize + 4),
        index: imageIndex,
        groupId: groupId,
        iterator: it
    }
    return res
}

function computePileLine(it: ImageIterator) {
    const group = it.sha1Group
    const res: PileRowLine = {
        id: group.id + '-sha1:' + String(group.images[0].sha1),
        data: group,
        type: 'pile',
        size: lineSizes[group.images[0].id] ?? (project.getTab().imageSize + 4),
        iterator: it
    }
    return res
}

function resizeHeight(item: ScrollerLine, h) {
    // console.log('resize')
    if (item.size == h) return
    item.size = h
    
    if (item.type == 'image') {
        lineSizes[item.data.id] = item.size
    }
    // setLines(dataLines, oldScroll)
}

let oldScroll = 0
let oldIndex = 0
function handleUpdate() {
    let newScroll = scroller.value.getScroll().start
    let sizes = scroller.value.sizes
    let length = rowLines.value.length
    let last = length - 1
    if (oldIndex > last) {
        oldScroll = 0
        oldIndex = 0
    }

    let newIndex = 0
    if (newScroll > oldScroll) {
        for (let i = oldIndex; i < length; i++) {
            newIndex = i
            if (sizes[i].accumulator > newScroll) break
        }
    } else {
        for (let i = oldIndex; i >= 0; i--) {
            newIndex = i
            if (sizes[i].accumulator - sizes[i].size < newScroll) break
        }
    }
    oldScroll = newScroll
    oldIndex = newIndex

    if(Math.abs(newScroll - lineCenter) > props.height) {
        setLines(dataLines, newScroll)
    }
}

function openGroup(groupId: string) {
    props.manager.openGroup(groupId, true)
    // computeLines()
}

function closeGroup(groupId: string) {
    props.manager.closeGroup(groupId, true)
    // computeLines()
}

function selectImage(groupId: string, imageIndex: number) {
    console.log(groupId, imageIndex)
    const iterator = props.manager.getImageIterator(groupId, imageIndex)
    props.manager.toggleImageIterator(iterator, keyState.shift)
    // props..toggleImageIterator(iterator, keyState.shift)
}

function selectGroup(groupId: string) {
    const iterator = props.manager.getGroupIterator(groupId)
    props.manager.toggleGroupIterator(iterator, keyState.shift)
}

function clear() {
    rowLines.value = []
}

function changeHandler(){
    computeLines()
    setLines(dataLines, 0)
}
onMounted(() => {
    props.manager.onChange.addListener(changeHandler)
    props.manager.clearCustomGroups(true)
})

onUnmounted(() => {
    props.manager.onChange.removeListener(changeHandler)
})

watch(() => project.getTab().imageSize, (now,old) => {
    let hook = 0
    let acc = 0
    for(const l of dataLines) {
        if(acc >= oldScroll) {
            hook = l.index
            break
        }
        acc += l.size
    }

    const currentLineIds = new Set(rowLines.value.map(l => l.index))
    dataLines.filter(l => !currentLineIds.has(l.index)).forEach(l => l.size = now)

    let goalPosition = 0
    acc = 0
    for(const l of dataLines) {
        if(l.index == hook) {
            goalPosition = acc
            break
        }
        acc += l.size
    }
    setLines(dataLines, goalPosition)

})

</script>

<template>
    <div class="grid-container overflow-hidden" :style="{ width: scrollerStyle.width }">
        <TableHeader :manager="props.manager" :properties="props.selectedProperties" :missing-width="missingWidth"
            :show-image="props.showImages" :current-group="currentGroup" class="p-0 m-0" />

        <RecycleScroller :items="rowLines" key-field="id" ref="scroller" :style="scrollerStyle" 
            :emitUpdate="true" :page-mode="false" :prerender="400" class="p-0 m-0" @scroll="handleUpdate"
            @scroll-start="handleUpdate">

            <template v-slot="{ item, index, active }">
                <template v-if="active && !hideFromModal">
                    <GridScrollerLine :item="item" :properties="props.selectedProperties" :width="scrollerWidth"
                        :show-images="props.showImages" :selected-images="props.manager.selectedImages"
                        :missing-width="missingWidth" @open:group="openGroup" @close:group="closeGroup"
                        @toggle:image="({ groupId, imageIndex }) => selectImage(groupId, imageIndex)" @toggle:group="selectGroup"
                        @resizeHeight="h => resizeHeight(item, h)" />
                </template>
                <!-- </DynamicScrollerItem> -->
            </template>
        </RecycleScroller>
    </div>
</template>

<style>
.grid-container {
    white-space: nowrap;
}
</style>