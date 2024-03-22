<script setup lang="ts">
// import RecycleScroller from '@/components/Scroller/src/components/RecycleScroller.vue';
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue';
import TableHeader from './TableHeader.vue';
import { keyState } from '@/data/keyState';
import { Group, GroupManager, GroupType, ImageIterator, ROOT_ID } from '@/core/GroupManager';
import { Property, GroupLine, Image, RowLine, PileRowLine, ScrollerLine, ModalId } from '@/data/models';
import { useProjectStore } from '@/data/projectStore';
import GridScrollerLine from './GridScrollerLine.vue';
import {RecycleScroller} from 'vue-virtual-scroller';
import { usePanopticStore } from '@/data/panopticStore';
const store = useProjectStore()
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
const lines = reactive([])
const lineSizes: { [id: string]: number } = {}
const scroller = ref(null)
const currentGroup = reactive({} as Group)

const totalPropWidth = computed(() => {
    const options = store.getTab().propertyOptions
    let propSum = props.selectedProperties.map(p => options[p.id].size).reduce((a, b) => a + b, 0)
    if (props.showImages) {
        propSum += store.getTab().imageSize
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


function computeLines() {
    console.time('Table compute lines')
    lines.length = 0

    let lastGroupId = undefined
    let current = props.manager.getImageIterator(undefined, undefined, { ignoreClosed: true })

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



    lines.push({ id: '__filler__', type: 'fillter', size: 1000 })
    scroller.value.updateVisibleItems(true)
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

function computeImageLine(it: ImageIterator, groupId: string, imageIndex) {
    const image = it.image
    const res: RowLine = {
        id: groupId + '-img:' + String(image.id),
        data: image,
        type: 'image',
        size: lineSizes[image.id] ?? (store.getTab().imageSize + 4),
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
        size: lineSizes[group.images[0].id] ?? (store.getTab().imageSize + 4),
        iterator: it
    }
    return res
}

function resizeHeight(item: ScrollerLine, h) {
    // console.log('resize')
    if (item.size == h) return
    // if(h < 35) return
    // console.log(item.data.id, item.size, h)
    item.size = h

    if (item.type == 'image') {
        lineSizes[item.data.id] = item.size
    }
    // scroller.value.updateVisibleItems(true)
}

let oldScroll = 0
let oldIndex = 0
function handleUpdate() {
    let newScroll = scroller.value.getScroll().start
    let sizes = scroller.value.sizes
    let length = lines.length
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

    let grpId = lines[newIndex].groupId
    // if (currentGroup.id != grpId) {
    //     Object.assign(currentGroup, props.data.index[grpId])
    // }
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
    lines.length = 0
}

const changeHandler = () => computeLines()
onMounted(() => {
    props.manager.onChange.addListener(changeHandler)
    props.manager.clearCustomGroups(true)
})

onUnmounted(() => {
    props.manager.onChange.removeListener(changeHandler)
})

</script>

<template>
    <div class="grid-container overflow-hidden" :style="{ width: scrollerStyle.width }">
        <TableHeader :manager="props.manager" :properties="props.selectedProperties" :missing-width="missingWidth"
            :show-image="props.showImages" :current-group="currentGroup" class="p-0 m-0" />

        <RecycleScroller :items="lines" key-field="id" ref="scroller" :style="scrollerStyle" :buffer="400"
            :emitUpdate="false" :page-mode="false" :prerender="0" class="p-0 m-0" @scroll="handleUpdate"
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