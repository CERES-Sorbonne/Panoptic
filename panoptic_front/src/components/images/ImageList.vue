<script setup>
import { globalStore } from '@/data/store';
import ImageVue from './Image.vue';
import { ref, nextTick, reactive, defineExpose, onMounted, watch, computed } from 'vue';
import DynamicScrollerItem from '@/components/Scroller/src/components/DynamicScrollerItem.vue'
import DynamicScroller from '@/components/Scroller/src/components/DynamicScroller.vue'
import ImageLine from './ImageLine.vue';
import GroupLine from './GroupLine.vue';
import RecycleScroller from '../Scroller/src/components/RecycleScroller.vue';

const props = defineProps({
    imageSize: Number,
    height: Number,
    width: Number,
    data: Object
})

const imageLines = reactive([])
const lineSizes = reactive({})

const scroller = ref(null)
const MARGIN_STEP = 20

const visiblePropertiesNb = computed(() => Object.values(globalStore.tabs[globalStore.selectedTab].data.visibleProperties).filter(v => v).length)

const maxPerLine = computed(() => Math.ceil(props.width / props.imageSize))

defineExpose({
    scroll
})

function computeLines() {
    // console.log('compute lines')
    let group = props.data.root
    const groupToLines = (group, lines, lineWidth, imgHeight) => {
        lines.push({
            id: group.id,
            type: 'group',
            data: group,
            depth: group.depth,
            size: 30,
            // index: lines.length
        })
        group.index = lines.length - 1
        if (Array.isArray(group.groups) && group.groups.length > 0) {
            group.groups.forEach(g => {
                groupToLines(g, lines, lineWidth, imgHeight)
            })
            return
        }
        if (Array.isArray(group.images) && group.images.length > 0) {
            computeImageLines(group.images, lines, imgHeight, lineWidth - (group.depth * MARGIN_STEP), group)
        }
    }

    let lines = []
    groupToLines(group, lines, props.width, props.imageSize)
    imageLines.length = 0
    imageLines.push(...lines)
    // console.log(lines)
    // nextTick(() => scroller.value.forceUpdate())
    return lines
}

function computeImageLines(images, lines, imageHeight, totalWidth, parentGroup) {
    let lineWidth = totalWidth
    let newLine = []
    let actualWidth = 0

    let addLine = (line) => {
        lines.push({
            id: parentGroup.id + '|img-' + lines.length,
            type: 'images',
            data: line,
            groupId: parentGroup.id,
            depth: parentGroup.depth,
            size: props.imageSize + (visiblePropertiesNb.value * 31) + 10,
            // index: lines.length
        })
    }

    for (let i = 0; i < images.length; i++) {
        let img = images[i]
        let imgWidth = imageHeight * img.containerRatio + 8
        if (actualWidth + imgWidth < lineWidth) {
            newLine.push(img)
            actualWidth += imgWidth
            continue
        }
        if (newLine.length == 0) {
            throw 'Images seems to be to big for the line'
        }
        addLine(newLine)
        newLine = []
        actualWidth = 0
    }

    if (newLine.length > 0) {
        addLine(newLine)
    }
}

function scrollToParent(currentId, dist=0) {
    let currentGroup = props.data.index[currentId]
    if(dist > 0) {
        scrollToParent(currentGroup.parentId, dist-1)
        return
    }
    let i = currentGroup.index
    scroller.value.scrollToItem(i)
}

onMounted(computeLines)

watch(() => props.data, computeLines, { deep: true })

watch(() => props.imageSize, () => {
    computeLines()
})

let resizeWidthHandler = undefined
watch(() => props.width, () => {
    clearTimeout(resizeWidthHandler)
    setTimeout(computeLines, 500)
})

</script>

<template>
    <DynamicScroller :items="imageLines" key-field="id" ref="scroller" :style="'height: ' + props.height + 'px;'"
        :buffer="800" :min-item-size="props.imageSize">
        <template v-slot="{ item, index, active }">
            <DynamicScrollerItem :item="item" :active="active" :data-index="index" :size-dependencies="[item.size]">

    <!-- <RecycleScroller class="scroller" :items="imageLines" key-field="id" v-slot="{ item, index, active }"> -->
        <div v-if="item.type == 'group'">
            <GroupLine :item="item" @scroll="dist => scrollToParent(item.id, dist+1)"/>
        </div>
        <div v-if="item.type == 'images'">
            <ImageLine :image-size="props.imageSize" :index="index * maxPerLine" :item="item" @scroll="dist => scrollToParent(item.groupId, dist)"/>
        </div>
    <!-- </RecycleScroller> -->
    </DynamicScrollerItem>
        </template>
    </DynamicScroller>
</template>

<style scoped>
.text-div {
    position: absolute;
    z-index: 900;
    background-color: wheat;
    top: 100px;
}
</style>
