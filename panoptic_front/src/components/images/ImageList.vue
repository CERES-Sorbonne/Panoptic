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
    rootGroup: Object
})

const imageLines = reactive([])
const lineSizes = reactive({})

const scroller = ref(null)
const MARGIN_STEP = 20

const visiblePropertiesNb = computed(() => Object.values(globalStore.tabs[globalStore.selectedTab].data.visibleProperties).filter(v => v).length)

function scroll() {
    scroller.value.scrollToItem(5)
    nextTick(() => scroller.value.forceUpdate())
    console.log(scroller.value)
}

const maxPerLine = computed(() => Math.ceil(props.width / props.imageSize))

defineExpose({
    scroll
})

function computeLines() {
    console.log('compute lines')
    let group = props.rootGroup
    const groupToLines = (group, lineWidth, imgHeight) => {
        let res = []
        res.push({
            id: group.id,
            type: 'group',
            data: group,
            depth: group.depth,
            size: 25
        })
        if (Array.isArray(group.groups) && group.groups.length > 0) {
            group.groups.forEach(g => {
                res.push(...groupToLines(g, lineWidth, imgHeight))
            })
            return res
        }
        if (Array.isArray(group.images) && group.images.length > 0) {
            let imgLines = computeImageLines(group.images, imgHeight, lineWidth - (group.depth * MARGIN_STEP), group)
            res.push(...imgLines)
        }

        return res
    }

    let lines = groupToLines(group, props.width, props.imageSize)
    imageLines.length = 0
    imageLines.push(...lines)
    console.log(lines)
    // nextTick(() => scroller.value.forceUpdate())
    return lines
}

function computeImageLines(images, imageHeight, totalWidth, parentGroup) {
    let lines = []
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
            size: props.imageSize + (visiblePropertiesNb.value * 31) + 10
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
    return lines
}

onMounted(computeLines)

watch(() => props.rootGroup, computeLines, { deep: true })

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
            <GroupLine :item="item" />
        </div>
        <div v-if="item.type == 'images'">
            <ImageLine :image-size="props.imageSize" :index="index * maxPerLine" :item="item" />
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
