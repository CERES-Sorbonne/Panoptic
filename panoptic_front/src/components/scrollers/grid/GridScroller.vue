<script setup lang="ts">
import RecycleScroller from '@/components/Scroller/src/components/RecycleScroller.vue';
import { Group, GroupData, GroupLine, Image, RowLine, Property, ScrollerLine, ImageLine, PileRowLine, Sha1Pile } from '@/data/models';
import { isImageGroup, isPileGroup } from '@/utils/utils';
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue';
import GroupLineVue from './GroupLine.vue';
import TableHeader from './TableHeader.vue';
import RowLineVue from './RowLine.vue';
import { globalStore } from '@/data/store';
import GridScrollerLine from './GridScrollerLine.vue';
import { GroupIterator, ImageIterator, groupParents } from '@/utils/groups';
import { ImageSelector } from '@/utils/selection';
import { keyState } from '@/data/keyState';


const props = defineProps({
    data: Object as () => GroupData,
    height: Number,
    width: Number,
    selectedProperties: Array<Property>,
    showImages: Boolean,
    selector: ImageSelector
})

defineExpose({
    // scrollTo,
    computeLines,
})


const hearderHeight = ref(60)
const lines = reactive([])
const lineSizes: { [id: string]: number } = {}
const scroller = ref(null)
const currentGroup = reactive({} as Group)

const totalPropWidth = computed(() => {
    const options = globalStore.getTab().data.propertyOptions
    let propSum = props.selectedProperties.map(p => options[p.id].size).reduce((a, b) => a + b, 0)
    if (props.showImages) {
        propSum += globalStore.getTab().data.imageSize
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

function computeLines() {
    lines.length = 0
    let maxDepth = -1
    for (let groupId of props.data.order) {
        const group = props.data.index[groupId]

        if (maxDepth != -1 && maxDepth >= group.depth) maxDepth = -1
        // if closed group all images inside group with depth > maxDeath should be hidden
        if (group.closed) {
            console.log(group.depth)
            maxDepth = group.depth
        }

        if (group.groups) continue
        if (isPileGroup(group)) {
            if (group.propertyValues.length > 0) {
                lines.push(computeGroupLine(group))
            }
            if (group.closed || (maxDepth < group.depth && maxDepth > -1)) continue
            const imageLines = group.imagePiles.map((pile, index) => computePileRow(pile, group.id, index))
            lines.push(...imageLines)
        }
        else if (isImageGroup(group)) {
            if (group.propertyValues.length > 0) {
                lines.push(computeGroupLine(group))
            }
            if (group.closed || (maxDepth < group.depth && maxDepth > -1)) continue
            const imageLines = group.images.map((img, index) => computeImageRow(img, group.id, index))
            lines.push(...imageLines)
        }
    }

    scroller.value.updateVisibleItems(true)
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

function computeImageRow(image: Image, groupId: string, imageIndex) {
    const res: RowLine = {
        id: groupId + '-img:' + String(image.id),
        data: image,
        type: 'image',
        size: lineSizes[image.id] ?? (globalStore.getTab().data.imageSize + 4),
        index: imageIndex,
        groupId: groupId
    }
    return res
}

function computePileRow(pile: Sha1Pile, groupId: string, imageIndex) {
    const res: PileRowLine = {
        id: groupId + '-sha1:' + String(pile.sha1),
        data: pile,
        type: 'pile',
        size: lineSizes[pile.images[0].id] ?? (globalStore.getTab().data.imageSize + 4),
        index: imageIndex,
        groupId: groupId
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
    if (currentGroup.id != grpId) {
        Object.assign(currentGroup, props.data.index[grpId])
    }
}

function openGroup(groupId: string) {
    const group = props.data.index[groupId]
    group.closed = false
    const groups = groupParents(props.data.index, group)
    groups.forEach(g => g.close = false)
    computeLines()
}

function closeGroup(groupId: string) {
    props.data.index[groupId].closed = true
    computeLines()
}

function selectImage(iterator: ImageIterator) {
    props.selector.toggleImageIterator(iterator, keyState.shift)
}

function selectGroup(iterator: GroupIterator) {
    console.log(iterator)
    props.selector.toggleGroupIterator(iterator, keyState.shift)
}

onMounted(computeLines)
watch(() => props.data, computeLines)

</script>

<template>
    <div class="grid-container overflow-hidden" :style="{ width: scrollerStyle.width }">
        <TableHeader :properties="props.selectedProperties" :missing-width="missingWidth" :show-image="props.showImages"
            :current-group="currentGroup" :data="props.data" class="p-0 m-0" />

        <RecycleScroller :items="lines" key-field="id" ref="scroller" :style="scrollerStyle" :buffer="400"
            :emitUpdate="false" :page-mode="false" :prerender="0" class="p-0 m-0" @scroll="handleUpdate"
            @scroll-start="handleUpdate">

            <template v-slot="{ item, index, active }">
                <template v-if="active">
                    <GridScrollerLine :item="item" :properties="props.selectedProperties" :width="scrollerWidth"
                        :show-images="props.showImages" :selected-images="props.selector.selectedImages" :data="props.data"
                        :missing-width="missingWidth" @open:group="openGroup" @close:group="closeGroup"
                        @toggle:image="selectImage" @toggle:group="selectGroup"
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