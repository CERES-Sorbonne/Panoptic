<script setup lang="ts">
import { ref, nextTick, reactive, defineExpose, onMounted, watch, computed } from 'vue';
import ImageLineVue from './ImageLine.vue';
import RecycleScroller from '@/components/Scroller/src/components/RecycleScroller.vue';
import PileLine from './PileLine.vue';
import GroupLineVue from './GroupLine.vue';
import { GroupManager, Group, GroupType, GroupIterator, ImageIterator } from '@/core/GroupManager';
import { keyState } from '@/data/keyState';
import { Property, Sha1Scores, ScrollerLine, PropertyMode, GroupLine, ScrollerPileLine, ImageLine, PropertyID } from '@/data/models';

const props = defineProps({
    imageSize: Number,
    height: Number,
    width: Number,
    groupManager: GroupManager,
    properties: Array<Property>,
    hideOptions: Boolean,
    hideGroup: Boolean,
    sha1Scores: Object as () => Sha1Scores
})

const emits = defineEmits(['recommend'])

const groupIdx = {}
const imageLines = reactive([]) as ScrollerLine[]

const hoverGroupBorder = ref('')

const scroller = ref(null)
const MARGIN_STEP = 20

const visiblePropertiesNb = computed(() => props.properties.length)
const visiblePropertiesCluster = computed(() => props.properties.filter(p => p.mode == PropertyMode.sha1 || (p.mode == PropertyMode.computed && p.id != PropertyID.id)))
const visiblePropertiesClusterNb = computed(() => visiblePropertiesCluster.value.length)

const maxPerLine = computed(() => Math.ceil(props.width / props.imageSize))

const imageLineSize = computed(() => {
    let nb = visiblePropertiesNb.value
    let offset = 0
    if (nb > 0) {
        offset += 28
    }
    if (nb > 1) {
        offset += (nb - 1) * 27
    }
    return props.imageSize + offset + 10
})

const pileLineSize = computed(() => {
    let nb = visiblePropertiesClusterNb.value
    let offset = 0
    if (nb > 0) {
        offset += 28
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
    clear
})

function clear() {
    imageLines.length = 0
}

function GroupToLines(it: GroupIterator) {
    const lines: Array<GroupLine | ScrollerPileLine> = []
    const group = it.group
    lines.push({
        id: group.id,
        type: 'group',
        data: group,
        depth: group.depth,
        size: props.hideGroup ? 0 : 30,
        nbClusters: 10
    })

    if (group.children.length > 0 && group.subGroupType != GroupType.Sha1) return lines
    if (group.view.closed) return lines

    if (group.subGroupType != GroupType.Sha1) {
        computeImageLines(it, lines, props.imageSize, props.width - (group.depth * MARGIN_STEP), group)
    } else {
        computeImagePileLines(it, lines as ScrollerPileLine[], props.imageSize, props.width - (group.depth * MARGIN_STEP), group)
    }

    return lines
}

function computeLines() {
    if (!props.groupManager.result.root) return
    clear()
    let it = props.groupManager.getGroupIterator()
    while (it) {
        const group = it.group
        groupIdx[group.id] = imageLines.length
        imageLines.push(...GroupToLines(it))
        it = it.nextGroup()
    }

    scroller.value.updateVisibleItems(true)
}

function computeImageLines(it: GroupIterator, lines, imageHeight, totalWidth, parentGroup, isSimilarities = false) {
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

    let imgIt = ImageIterator.fromGroupIterator(it)
    while (imgIt && imgIt.groupId == it.groupId) {

        let img = imgIt.image
        let imgWidth = (imageHeight * img.containerRatio) + 10
        if (actualWidth + imgWidth < lineWidth) {
            newLine.push(imgIt)
            actualWidth += imgWidth
            imgIt = imgIt.nextImages()
            continue
        }
        if (newLine.length == 0) {
            // newLine.push(img)
            throw new Error('Images seems to be to big for the line')
        }
        addLine(newLine)
        newLine = [imgIt]
        actualWidth = imgWidth

        imgIt = imgIt.nextImages()
    }

    if (newLine.length > 0) {
        addLine(newLine)
    }
}

function computeImagePileLines(it: GroupIterator, lines: ScrollerPileLine[], imageHeight, totalWidth, parentGroup) {
    let lineWidth = totalWidth
    let newLine: ImageIterator[] = []
    let actualWidth = 0

    let addLine = (line: ImageIterator[]) => {
        lines.push({
            id: parentGroup.id + '|img-' + lines.length,
            type: 'piles',
            data: line,
            groupId: parentGroup.id,
            depth: parentGroup.depth + 1,
            size: pileLineSize.value
        })
    }

    let imgIt = ImageIterator.fromGroupIterator(it)
    while (imgIt && imgIt.groupId == it.groupId) {
        let group = imgIt.sha1Group
        let img = imgIt.image
        let imgWidth = (imageHeight * img.containerRatio) + 10
        if (actualWidth + imgWidth < lineWidth) {
            newLine.push(imgIt)
            actualWidth += imgWidth
            imgIt = imgIt.nextImages()
            continue
        }
        if (newLine.length == 0) {
            // newLine.push(group)
            throw new Error('Images seems to be to big for the line')
        }
        addLine(newLine)
        newLine = [imgIt]
        actualWidth = imgWidth

        imgIt = imgIt.nextImages()
    }

    if (newLine.length > 0) {
        addLine(newLine)
    }
}

function scrollTo(groupId) {
    const idx = groupIdx[groupId]
    scroller.value.scrollToItem(idx)
    nextTick(() => scroller.value.updateVisibleItems(true))
}

function updateHoverBorder(value) {
    hoverGroupBorder.value = value
}

function getParents(group: Group) {
    if (group && group.id != undefined) {
        if (group.parent != undefined) {
            return [...getParents(group.parent), group.parent.id]
        }
    }
    return []
}

function getImageLineParents(item) {
    return [...getParents(props.groupManager.result.index[item.groupId]), item.groupId]
}

function closeGroup(groupIds) {
    computeLines()
}

function openGroup(groupId) {
    let index = imageLines.findIndex(line => line.id == groupId)
    if (index < 0) {
        return
    }

    computeLines()

}

function updateImageSelection(data: { id: number, value: boolean }, item: ImageLine) {
    const iterator = props.groupManager.findImageIterator(item.groupId, data.id)
    props.groupManager.toggleImageIterator(iterator, keyState.shift)
}

function toggleGroupSelect(groupId: string) {
    const iterator = props.groupManager.getGroupIterator(groupId)
    props.groupManager.toggleGroupIterator(iterator, keyState.shift)
}


onMounted(computeLines)

watch(() => props.imageSize, () => {
    console.log('image size compute')
    nextTick(computeLines)
})

watch(visiblePropertiesNb, () => {
    // console.time('update-visible')
    let scroll = scroller.value.getScroll().start
    let totalSize = scroller.value.totalSize
    let ratio = scroll / totalSize

    imageLines.forEach(l => {
        if (l.type == 'images') {
            l.size = imageLineSize.value
        }
        else if (l.type == 'piles') {
            l.size = pileLineSize.value
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
        :buffer="800" :min-item-size="props.imageSize" :emitUpdate="false" @update="" :page-mode="false" :prerender="0">
        <template v-slot="{ item, index, active }">
            <template v-if="active">
                <!-- <DynamicScrollerItem :item="item" :active="active" :data-index="index" :size-dependencies="[item.size]"> -->
                <div v-if="item.type == 'group' && !props.hideGroup">
                    <GroupLineVue :item="item" :hover-border="hoverGroupBorder" :parent-ids="getParents(item.data)"
                        :manager="props.groupManager" :hide-options="props.hideOptions" :data="props.groupManager.result"
                        @scroll="scrollTo" @hover="updateHoverBorder" @unhover="hoverGroupBorder = ''"
                        @group:close="closeGroup" @group:open="openGroup" @select="toggleGroupSelect"
                        @recommend="(groupId) => emits('recommend', groupId)" />
                </div>
                <div v-else-if="item.type == 'images'">
                    <!-- +1 on imageSize to avoid little gap. TODO: Find if there is a real fix -->
                    <ImageLineVue :image-size="props.imageSize + 1" :input-index="index * maxPerLine" :item="item"
                        :index="props.groupManager.result.index" :hover-border="hoverGroupBorder"
                        :parent-ids="getImageLineParents(item)" :properties="props.properties"
                        :selected-images="props.groupManager.selectedImages"
                        @update:selected-image="e => updateImageSelection(e, item)" @scroll="scrollTo"
                        @hover="updateHoverBorder" @unhover="hoverGroupBorder = ''" @update="computeLines()" />
                </div>
                <div v-else-if="item.type == 'piles'">
                    <PileLine :image-size="props.imageSize + 1" :input-index="index * maxPerLine" :item="item"
                        :index="props.groupManager.result.index" :hover-border="hoverGroupBorder"
                        :parent-ids="getImageLineParents(item)" :properties="visiblePropertiesCluster"
                        :selected-images="props.groupManager.selectedImages" :sha1-scores="props.sha1Scores"
                        @update:selected-image="e => updateImageSelection(e, item)" @scroll="scrollTo"
                        @hover="updateHoverBorder" @unhover="hoverGroupBorder = ''" @update="computeLines()" />
                </div>
                <div v-else-if="item.type == 'filler'">
                    <div :style="{ height: item.size + 'px' }" class=""></div>
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
