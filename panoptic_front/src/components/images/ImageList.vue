<script setup>
import { globalStore } from '@/data/store';
import ImageVue from './Image.vue';
import { ref, nextTick, reactive, defineExpose, onMounted, watch, computed } from 'vue';
import DynamicScrollerItem from '@/components/Scroller/src/components/DynamicScrollerItem.vue'
import DynamicScroller from '@/components/Scroller/src/components/DynamicScroller.vue'

const props = defineProps({
    imageSize: Number,
    height: Number,
    width: Number
})

const imageLines = reactive([])
const lineSizes = reactive({})

const scroller = ref(null)

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
    imageLines.length = 0
    let images = Object.values(globalStore.images)

    let lineWidth = props.width
    let newLine = []
    let actualWidth = 0

    let addLine = (line) => { imageLines.push({ id: imageLines.length, images: line, size: props.imageSize }) }

    for (let i = 0; i < images.length; i++) {
        let img = images[i]
        let imgWidth = props.imageSize * img.containerRatio + 10
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

onMounted(() => {
    nextTick(computeLines)
})

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
    <!-- <div class="d-flex flex-wrap">
        <Image :image="image" v-for="image, index in globalStore.images" :index="index" groupId="0" />
    </div> -->
    <!-- {{ Object.values(globalStore.images) }} -->
    <DynamicScroller :items="imageLines" key-field="id" ref="scroller" :style="'height: ' + props.height + 'px;'"
        :buffer="400" :min-item-size="props.imageSize">
        <template v-slot="{ item, index, active }">
            <DynamicScrollerItem :item="item" :active="active" :data-index="index"  >
                <div class="d-flex flex-row">
                    <ImageVue :image="image" :index="(index * maxPerLine) + i" groupId="0" :size="props.imageSize"
                        v-for="image, i in item.images" />
                </div>

            </DynamicScrollerItem>
        </template>
    </DynamicScroller>

    <!-- <InfiniteList :data="imageLines" :width="props.width" :height="props.height" :item-size="props.imageSize" ref="scroller"
        v-slot="{ item, index }">
        <div class="d-flex flex-row">

            <ImageVue :image="image" :index="(index * maxPerLine) + i" groupId="0" :size="props.imageSize"
                v-for="image, i in item.images"/>
        </div>
    </InfiniteList> -->
</template>

<style scoped>

.text-div {
    position: absolute;
    z-index: 900;
    background-color: wheat;
    top: 100px;
}
</style>
