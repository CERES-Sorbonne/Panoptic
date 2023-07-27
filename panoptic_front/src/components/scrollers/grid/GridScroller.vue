<script setup lang="ts">
import RecycleScroller from '@/components/Scroller/src/components/RecycleScroller.vue';
import { Group, GroupData, GroupLine, Image, RowLine, Property } from '@/data/models';
import { isImageGroup } from '@/utils/utils';
import { computed, onMounted, reactive, ref, watch } from 'vue';
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


const hearderHeight = ref(30)
const lines = reactive([])
const scroller = ref(null)

const scrollerWidth = computed(() => {
    const options = globalStore.getTab().data.propertyOptions
    const propSum = props.selectedProperties.map(p => options[p.id].size).reduce((a, b) => a + b, 0)
    return propSum + globalStore.getTab().data.imageSize + 2
})

const scrollerHeight = computed(() => props.height - hearderHeight.value)

const scrollerStyle = computed(() => ({
    height: scrollerHeight.value + 'px',
    width: scrollerWidth.value + 'px',
    // overflow: 'hidden'
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
}

function computeGroupLine(group: Group) {
    // console.log(group)
    const res: GroupLine = {
        id: group.id,
        data: group,
        type: 'group',
        size: 30,
        nbClusters: 10
    }
    return res
}

function computeImageRow(image: Image, groupId: string, groupIndex) {
    const res: RowLine = {
        id: groupId + '-img:' + String(image.id),
        data: image,
        type: 'image',
        size: 30,
        index: groupIndex
    }
    return res
}

function resizeHeight(item, h) {
    // console.log('resize')
    item.size = h
    scroller.value.updateVisibleItems(true)
}

onMounted(computeLines)
watch(() => props.data, computeLines)

</script>

<template>
    <div class="grid-container overflow-hidden" :style="{width: scrollerStyle.width}">
        <div class="mt-1"></div>
        <TableHeader :properties="props.selectedProperties" :show-image="props.showImages" class="p-0 m-0" />

        <RecycleScroller :items="lines" key-field="id" ref="scroller" :style="scrollerStyle" :buffer="200"
            :emitUpdate="false" @update="" :page-mode="false" :prerender="0" class="p-0 m-0">

            <template v-slot="{ item, index, active }">
                <template v-if="active">
                    <!-- <div v-if="item.type == 'group'">
                        <GroupLineVue :prop-values="item.data.propertyValues" :item="item" :width="scrollerWidth" />
                    </div>
                    <div v-if="item.type == 'image'">
                        <RowLineVue :item="item" :properties="props.selectedProperties" :show-image="props.showImages"
                            @resizeHeight="h => resizeHeight(item, h)" />
                    </div> -->
                    <GridScrollerLine :item="item" :properties="props.selectedProperties" :width="scrollerWidth" @resizeHeight="h => resizeHeight(item, h)" :show-images="true"/>
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