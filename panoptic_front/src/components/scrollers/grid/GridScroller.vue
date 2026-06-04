<script setup lang="ts">
// import RecycleScroller from '@/components/Scroller/src/components/RecycleScroller.vue';
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue';
import TableHeader from './TableHeader.vue';
import { keyState } from '@/data/keyState';
import { Group, GroupManager, GroupType, ImageIterator } from '@/core/GroupManager';
import { Property, GroupLine, RowLine, PileRowLine, ScrollerLine, ModalId, PropertyMode } from '@/data/models';
import { useProjectStore } from '@/data/projectStore';
import GridScrollerLine from './GridScrollerLine.vue';
import {RecycleScroller} from 'vue-virtual-scroller';
import { usePanopticStore } from '@/data/panopticStore';
import { useColumnStore } from '@/data/columnStore';
import { TabManager } from '@/core/TabManager';
import InstanceData from '@/components/data/InstanceData.vue';

const project = useProjectStore()
const panoptic = usePanopticStore()
const columnStore = useColumnStore()

const props = defineProps({
    tab: TabManager,
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
const visibleProperties = computed(() => props.selectedProperties.filter(p => {
    return p.mode == PropertyMode.sha1 || props.manager.state.sha1Mode == false
}))

const tabState = computed(() => props.tab.state)

const windowStart = ref(0)
const windowEnd = ref(0)

function onScrollerUpdate(startIndex: number, endIndex: number) {
    windowStart.value = startIndex
    windowEnd.value = endIndex
}

const totalPropWidth = computed(() => {
    const options =tabState.value.propertyOptions
    let propSum = visibleProperties.value.map(p => options[p.id]?.size ?? 0).reduce((a, b) => a + b, 0)
    if (props.showImages) {
        propSum += tabState.value.imageSize
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

const hideFromModal = computed(() => props.hideIfModal && (panoptic.openModalId == ModalId.IMAGE || panoptic.openModalId == ModalId.TAG))

const windowIds = computed(() => {
    const ids: number[] = []
    const lines = rowLines.value
    if (!lines.length) return ids

    let start = Math.max(0, Math.min(windowStart.value, lines.length - 1))
    let end   = Math.max(0, Math.min(windowEnd.value,   lines.length - 1))

    let preCount = 0
    while (start > 0 && preCount < 5) {
        start--
        if (lines[start].type === 'image' || lines[start].type === 'pile') preCount++
    }
    let postCount = 0
    while (end < lines.length - 1 && postCount < 5) {
        end++
        if (lines[end].type === 'image' || lines[end].type === 'pile') postCount++
    }

    const colIds = columnStore.instanceIds()
    for (let i = start; i <= end; i++) {
        const line = lines[i]
        if (line.type === 'image') {
            ids.push((line as RowLine).data.id)
        } else if (line.type === 'pile') {
            for (const slot of (line as PileRowLine).data.slots) ids.push(colIds[slot])
        }
    }
    return ids
})

const windowPropIds = computed(() => visibleProperties.value.map(p => p.id))

let dataLines = []
function computeLines() {
    if (!props.manager.result.root) return
    console.time('Table compute lines')
    const lines = []

    let lastGroupId = undefined
    let current = props.manager.getImageIterator(undefined, undefined, { ignoreClosed: true })
    // lines.push({ id: '__filler__', type: 'fillter', size: 0, index: lines.length })
    while (current) {
        const group = current.group
        if (lastGroupId != group.id && group.id !== 0) {
            lines.push(computeGroupLine(group))
            lastGroupId = group.id
        }
        if (!group.view.closed && group.slots.length) {
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
    rowLines.value = lines
    scroller.value?.updateVisibleItems(true)
    console.timeEnd('Table compute lines')
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

function computeImageLine(it: ImageIterator, groupId: number, imageIndex) {
    const instanceId = columnStore.instanceIds()[it.slot]
    const defaultSize = props.showImages ? tabState.value.imageSize + 4 : 28
    const res: RowLine = {
        id: groupId + '-img:' + String(instanceId),
        data: { id: instanceId, imageUrl: '' },
        type: 'image',
        size: lineSizes[instanceId] ?? defaultSize,
        index: imageIndex,
        groupId: groupId,
        iterator: it
    }
    return res
}

function computePileLine(it: ImageIterator) {
    const group = it.sha1Group
    const firstId = columnStore.instanceIds()[group.slots[0]]
    const defaultSize = props.showImages ? tabState.value.imageSize + 4 : 28
    const res: PileRowLine = {
        id: group.id + '-sha1:' + String(firstId),
        data: group,
        type: 'pile',
        size: lineSizes[firstId] ?? defaultSize,
        iterator: it
    }
    return res
}

function resizeHeight(item: ScrollerLine, h) {
    if (item.size == h) return
    item.size = h
    if (item.type == 'image') {
        lineSizes[(item as RowLine).data.id] = item.size
    } else if (item.type == 'pile') {
        const firstId = columnStore.instanceIds()[(item as PileRowLine).data.slots[0]]
        if (firstId !== undefined) lineSizes[firstId] = item.size
    }
}


function openGroup(groupId: number) {
    props.manager.openGroup(groupId, true)
    // computeLines()
}

function closeGroup(groupId: number) {
    props.manager.closeGroup(groupId, true)
    // computeLines()
}

function selectImage(groupId: number, imageIndex: number) {
    // console.log(groupId, imageIndex)
    const iterator = props.manager.getImageIterator(groupId, imageIndex)
    props.manager.toggleImageIterator(iterator, keyState.shift)
    // props..toggleImageIterator(iterator, keyState.shift)
}

function selectGroup(groupId: number) {
    const iterator = props.manager.getGroupIterator(groupId)
    props.manager.toggleGroupIterator(iterator, keyState.shift)
}

function clear() {
    rowLines.value = []
}

function changeHandler(){
    computeLines()
}
onMounted(() => {
    props.manager.onResultChange.addListener(changeHandler)
    props.manager.clearCustomGroups(true)
})

onUnmounted(() => {
    props.manager.onResultChange.removeListener(changeHandler)
})

watch(() => tabState.value.imageSize, (now) => {
    if (!scroller.value || !dataLines.length) return
    const scrollPos = scroller.value.getScroll().start

    let topIdx = 0
    let acc = 0
    for (let i = 0; i < dataLines.length; i++) {
        if (acc + dataLines[i].size > scrollPos) { topIdx = i; break }
        acc += dataLines[i].size
    }

    const visibleIds = new Set(rowLines.value.slice(windowStart.value, windowEnd.value + 1).map((l: any) => l.id))
    dataLines.forEach(l => {
        if (!visibleIds.has(l.id) && (l.type === 'image' || l.type === 'pile')) l.size = now + 4
    })

    let newScrollPos = 0
    for (let i = 0; i < topIdx; i++) newScrollPos += dataLines[i].size
    scroller.value.scrollToPosition(newScrollPos)
})

</script>

<template>
    <div class="grid-container overflow-hidden" :style="{ width: scrollerStyle.width }">
        <TableHeader :tab="props.tab" :manager="props.manager" :properties="visibleProperties" :missing-width="missingWidth"
            :show-image="props.showImages" :current-group="currentGroup" class="p-0 m-0" />

        <InstanceData :instance-ids="windowIds" :prop-ids="windowPropIds">
        <RecycleScroller :items="rowLines" key-field="id" ref="scroller" :style="scrollerStyle"
            :emitUpdate="true" :page-mode="false" :prerender="400" class="p-0 m-0" @update="onScrollerUpdate">

            <template v-slot="{ item, index, active }">
                <template v-if="active && !hideFromModal">
                    <GridScrollerLine :item="item" :tab="props.tab" :properties="visibleProperties" :width="scrollerWidth"
                        :show-images="props.showImages" :selected-images="props.manager.selectedImages"
                        :missing-width="missingWidth" @open:group="openGroup" @close:group="closeGroup"
                        @toggle:image="({ groupId, imageIndex }) => selectImage(groupId, imageIndex)" @toggle:group="selectGroup"
                        @resizeHeight="h => resizeHeight(item, h)" />
                </template>
            </template>
        </RecycleScroller>
        </InstanceData>
    </div>
</template>

<style>
.grid-container {
    white-space: nowrap;
}
</style>