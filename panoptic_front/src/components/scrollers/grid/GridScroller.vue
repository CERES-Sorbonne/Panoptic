<script setup lang="ts">
import RecycleScroller from '@/components/Scroller/src/components/RecycleScroller.vue';
import { Group, GroupData, GroupLine, Image, RowLine, Property, ScrollerLine, ImageLine } from '@/data/models';
import { isImageGroup } from '@/utils/utils';
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue';
import GroupLineVue from './GroupLine.vue';
import TableHeader from './TableHeader.vue';
import RowLineVue from './RowLine.vue';
import { globalStore } from '@/data/store';
import GridScrollerLine from './GridScrollerLine.vue';


const props = defineProps({
    data: Object as () => GroupData,
    height: Number,
    width: Number,
    selectedProperties: Array<Property>,
    showImages: Boolean
})

defineExpose({
    // scrollTo,
    computeLines,
})


const hearderHeight = ref(60)
const lines = reactive([])
const lineSizes: {[id: string]: number} = {}
const scroller = ref(null)
const currentGroup = reactive({} as Group)

const scrollerWidth = computed(() => {
    const options = globalStore.getTab().data.propertyOptions
    let propSum = props.selectedProperties.map(p => options[p.id].size).reduce((a, b) => a + b, 0)
    if(props.showImages) {
        propSum += globalStore.getTab().data.imageSize
    }
    return propSum + 1
})

const scrollerHeight = computed(() => props.height - hearderHeight.value)

const scrollerStyle = computed(() => ({
    height: scrollerHeight.value + 'px',
    width: scrollerWidth.value + 'px',
    // overflowX: 'hidden'
}))

function computeLines() {
    lines.length = 0

    const recursive = function (group: Group) {
        if (group.groups) {
            group.groups.forEach(g => recursive(g))
        }
        else if (isImageGroup(group)) {
            if (group.propertyValues.length > 0)
                lines.push(computeGroupLine(group))

            const imageLines = group.images.map((img, index) => computeImageRow(img, group.id, index))
            lines.push(...imageLines)
        }
    }
    if (props.data.root) {
        console.log('compute lines')
        recursive(props.data.root)
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

function computeImageRow(image: Image, groupId: string, groupIndex) {
    const res: RowLine = {
        id: groupId + '-img:' + String(image.id),
        data: image,
        type: 'image',
        size: lineSizes[image.id] ?? (globalStore.getTab().data.imageSize + 4),
        index: groupIndex,
        groupId: groupId
    }
    return res
}

function resizeHeight(item: ScrollerLine, h) {
    // console.log('resize')
    if(item.size == h) return
    // if(h < 35) return
    // console.log(item.data.id, item.size, h)
    item.size = h
    
    if(item.type == 'image') {
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
    let last = length -1
    if(oldIndex > last) {
        oldScroll = 0
        oldIndex = 0
    }

    let newIndex = 0
    if(newScroll > oldScroll) {
        for(let i = oldIndex; i < length; i++) {
            newIndex = i
            if(sizes[i].accumulator > newScroll) break
        }
    } else {
        for(let i = oldIndex; i >=0; i-- ) {
            newIndex = i
            if(sizes[i].accumulator - sizes[i].size < newScroll) break
        }
    }
    oldScroll = newScroll
    oldIndex = newIndex
    
    let grpId = lines[newIndex].groupId
    if(currentGroup.id != grpId) {
        Object.assign(currentGroup, props.data.index[grpId])
    }
}

onMounted(computeLines)
watch(() => props.data, computeLines)

</script>

<template>
    <div class="grid-container overflow-hidden" :style="{width: scrollerStyle.width}">
        <div class="mt-1"></div>
        <TableHeader :properties="props.selectedProperties" :show-image="props.showImages" :current-group="currentGroup" :data="props.data" class="p-0 m-0" />

        <RecycleScroller :items="lines" key-field="id" ref="scroller" :style="scrollerStyle" :buffer="400"
            :emitUpdate="false" :page-mode="false" :prerender="0" class="p-0 m-0" @scroll="handleUpdate" @scroll-start="handleUpdate" >

            <template v-slot="{ item, index, active }">
                <template v-if="active">
                    <GridScrollerLine :item="item" :properties="props.selectedProperties" :width="scrollerWidth" @resizeHeight="h => resizeHeight(item, h)" :show-images="props.showImages"/>
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