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

const hoverGroupBorder = ref('')

const scroller = ref(null)
const MARGIN_STEP = 20

const visiblePropertiesNb = computed(() => Object.values(globalStore.tabs[globalStore.selectedTab].data.visibleProperties).filter(v => v).length)

const maxPerLine = computed(() => Math.ceil(props.width / props.imageSize))

defineExpose({
    scroll,
    computeLines
})

function computeLines() {
    console.log('compute lines')
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
    console.log(imageLines.length)
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
            depth: parentGroup.depth + 1,
            size: props.imageSize + (visiblePropertiesNb.value * 31) + 10,
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

function scrollTo(groupId) {
    let group = props.data.index[groupId]
    let i = group.index
    scroller.value.scrollToItem(i)
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
    if (!Array.isArray(groupIds)) {
        groupIds = [groupIds]
    }
    groupIds.forEach(groupId => {
        let index = imageLines.findIndex(line => line.id == groupId)
        if (index < 0) {
            return
        }

        let depth = imageLines[index].depth
        let end = index
        // console.log('start', index, depth)
        for (let i = index + 1; i < imageLines.length; i++) {
            // console.log(imageLines[i].depth)
            if (imageLines[i].depth <= depth)
                break
            end = i
        }
        console.log(index, end)
        imageLines.splice(index + 1, end - index)
    })

    scroller.value.updateVisibleItems(true)

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
    computeLines()
})

watch(visiblePropertiesNb, () => {
    imageLines.forEach(l => {
        if (l.type == 'images') {
            l.size = props.imageSize + (visiblePropertiesNb.value * 31) + 10
        }
    })
})

let resizeWidthHandler = undefined
watch(() => props.width, () => {
    clearTimeout(resizeWidthHandler)
    setTimeout(computeLines, 500)
})


</script>

<template>
    <RecycleScroller :items="imageLines" key-field="id" ref="scroller" :style="'height: ' + props.height + 'px;'"
        :buffer="800" :min-item-size="props.imageSize" :emitUpdate="false" @update="">
        <template v-slot="{ item, index, active }">
            <!-- <DynamicScrollerItem :item="item" :active="active" :data-index="index" :size-dependencies="[item.size]"> -->
            <div v-if="item.type == 'group'">
                <GroupLine :item="item" :hover-border="hoverGroupBorder" :parent-ids="getParents(item.data)"
                    :index="props.data.index" @scroll="scrollTo" @hover="updateHoverBorder" @unhover="hoverGroupBorder = ''"
                    @group:close="closeGroup" @group:open="openGroup" @group:update="computeLines" />
            </div>
            <div v-else-if="item.type == 'images'">
                <ImageLine :image-size="props.imageSize" :index="index * maxPerLine" :item="item"
                    :hover-border="hoverGroupBorder" :parent-ids="getImageLineParents(item)" @scroll="scrollTo"
                    @hover="updateHoverBorder" @unhover="hoverGroupBorder = ''" />
            </div>
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
