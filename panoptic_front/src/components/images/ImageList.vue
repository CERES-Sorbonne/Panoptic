<script setup>
import { globalStore } from '@/data/store';
import { ref, nextTick, reactive, defineExpose, onMounted, watch, computed } from 'vue';
import ImageLine from './ImageLine.vue';
import GroupLine from './GroupLine.vue';
import RecycleScroller from '../Scroller/src/components/RecycleScroller.vue';

const props = defineProps({
    imageSize: Number,
    height: Number,
    width: Number,
    data: Object
})

const emits = defineEmits(['recommend'])

const imageLines = reactive([])

const hoverGroupBorder = ref('')

const scroller = ref(null)
const MARGIN_STEP = 20

const visiblePropertiesNb = computed(() => Object.values(globalStore.tabs[globalStore.selectedTab].data.visibleProperties).filter(v => v).length)

const maxPerLine = computed(() => Math.ceil(props.width / props.imageSize))

const imageLineSize = computed(() => {
    let nb = visiblePropertiesNb.value
    let offset = 0
    if (nb > 0) {
        offset += 31
    }
    if (nb > 1) {
        offset += (nb - 1) * 27
    }
    return props.imageSize + offset + 10
})

const simiImageLineSize = computed(() => {
    return props.imageSize + 40
})


defineExpose({
    scrollTo,
    computeLines,
})

let _flagCompute = false
function computeLines() {
    if(_flagCompute) {
        return
    }
    _flagCompute = true
    console.time('compute lines')
    let group = props.data.root
    let index = props.data.index
    const groupToLines = (group, lines, lineWidth, imgHeight) => {
        lines.push({
            id: group.id,
            type: 'group',
            data: group,
            depth: group.depth,
            size: 30,
            nbClusters: 10
            // index: lines.length
        })
        group.index = lines.length - 1
        if (!group.closed && Array.isArray(group.groups) && group.groups.length > 0) {
            group.groups.forEach(g => {
                groupToLines(g, lines, lineWidth, imgHeight)
            })
            return
        }
        // if (!group.closed && Array.isArray(group.allSimilarSha1s) && group.allSimilarSha1s.length > 0) {
        //     computeImageLines(group.getSimilarImages(), lines, imgHeight, lineWidth - (group.depth * MARGIN_STEP), group, true)
        // }
        if (!group.closed && Array.isArray(group.images) && group.images.length > 0) {
            computeImageLines(group.images, lines, imgHeight, lineWidth - (group.depth * MARGIN_STEP), group)
        }
    }

    let lines = []
    groupToLines(index[group.id], lines, props.width, props.imageSize)
    imageLines.length = 0
    imageLines.push(...lines)

    // console.log(lines)
    scroller.value.updateVisibleItems(true)
    // console.log(imageLines.length)
    console.timeEnd('compute lines')

    nextTick(() => _flagCompute = false)
    return lines
}

function computeImageLines(images, lines, imageHeight, totalWidth, parentGroup, isSimilarities = false) {
    let lineWidth = totalWidth
    let newLine = []
    let actualWidth = 0

    let addLine = (line) => {
        lines.push({
            id: parentGroup.id + '|img-' + lines.length,
            type: 'images',
            data: line,
            groupId: parentGroup.id,
            depth: parentGroup.depth + 1,
            size: isSimilarities ? simiImageLineSize.value : imageLineSize.value,
            isSimilarities: isSimilarities
        })
    }

    for (let i = 0; i < images.length; i++) {
        let img = images[i]
        let imgWidth = (imageHeight * img.containerRatio) + 10
        if (actualWidth + imgWidth < lineWidth) {
            newLine.push(img)
            actualWidth += imgWidth
            continue
        }
        if (newLine.length == 0) {
            throw 'Images seems to be to big for the line'
        }
        addLine(newLine)
        newLine = [img]
        actualWidth = imgWidth
    }

    if (newLine.length > 0) {
        addLine(newLine)
    }
}

function scrollTo(groupId) {
    let group = props.data.index[groupId]
    let i = group.index
    scroller.value.scrollToItem(i)
    nextTick(() => scroller.value.updateVisibleItems(true))
}

function updateHoverBorder(value) {
    hoverGroupBorder.value = value
}

function getParents(group) {
    // if (item.groupId != undefined) {
    //     return [...getParents(props.data.index[item.groupId]), item.groupId]
    // }
    if (group && group.id != undefined) {
        if (group.parentId != undefined) {
            return [...getParents(props.data.index[group.parentId]), group.parentId]
        }
    }
    return []
}

function getImageLineParents(item) {
    return [...getParents(props.data.index[item.groupId]), item.groupId]
}

function closeGroup(groupIds) {
    computeLines()

    // scroller.value.updateVisibleItems(true)

}

function openGroup(groupId) {
    let index = imageLines.findIndex(line => line.id == groupId)
    if (index < 0) {
        return
    }

    computeLines()

}

onMounted(computeLines)
// onMounted(() => updateListWindow(0, 100))

// watch(() => props.data, () => {
//     console.log('props.data watch')
//     computeLines()
// }, { deep: true })

watch(() => props.imageSize, () => {
    console.log('image size compute')
    nextTick(computeLines)
})

watch(visiblePropertiesNb, () => {
    // console.time('update-visible')
    let scroll = scroller.value.getScroll().start
    let totalSize = scroller.value.totalSize
    let ratio = scroll / totalSize
    let size = imageLineSize.value
    imageLines.forEach(l => {
        if (l.type == 'images') {
            l.size = size
        }
    })
    // scroller.value.updateVisibleItems(true)
    nextTick(() => {
        let goal = scroller.value.totalSize * ratio

        scroller.value.scrollToPosition(goal)
        scroller.value.updateVisibleItems(true)
        nextTick(() => {
            scroller.value.scrollToPosition(goal - 10)
            nextTick(() => scroller.value.updateVisibleItems(true))
        })
        nextTick(() => scroller.value.updateVisibleItems(true))
        // requestIdleCallback(() => requestIdleCallback(() => scroller.value.updateVisibleItems(false, true)))
    })
    // console.timeEnd('update-visible')
})

let resizeWidthHandler = undefined
watch(() => props.width, () => {
    clearTimeout(resizeWidthHandler)
    setTimeout(computeLines, 500)
})

</script>

<template>
    <RecycleScroller :items="imageLines" key-field="id" ref="scroller" :style="'height: ' + props.height + 'px;'"
        :buffer="800" :min-item-size="props.imageSize" :emitUpdate="false" @update="" :page-mode="false" :prerender="200">
        <template v-slot="{ item, index, active }">
            <template v-if="active">
                <!-- <DynamicScrollerItem :item="item" :active="active" :data-index="index" :size-dependencies="[item.size]"> -->
                <div v-if="item.type == 'group'">
                    <GroupLine :item="item" :hover-border="hoverGroupBorder" :parent-ids="getParents(item.data)"
                        :index="props.data.index" @scroll="scrollTo" @hover="updateHoverBorder"
                        @unhover="hoverGroupBorder = ''" @group:close="closeGroup" @group:open="openGroup"
                        @group:update="computeLines"  @recommend="(imgs, values, groupId) => emits('recommend', imgs, values, groupId)"/>
                </div>
                <div v-else-if="item.type == 'images'">
                    <ImageLine :image-size="props.imageSize" :input-index="index * maxPerLine" :item="item"
                        :index="props.data.index" :hover-border="hoverGroupBorder" :parent-ids="getImageLineParents(item)"
                        @scroll="scrollTo" @hover="updateHoverBorder" @unhover="hoverGroupBorder = ''"
                        @update="computeLines()"/>
                </div>
                <div v-else-if="item.type == 'similarity'">
                    
                </div>
            </template>
            <!-- </DynamicScrollerItem> -->
        </template>
    </RecycleScroller>
    <!-- </RecycleScroller> -->
</template>

<style scoped>
.text-div {
    position: absolute;
    z-index: 900;
    background-color: wheat;
    top: 100px;
}
</style>
