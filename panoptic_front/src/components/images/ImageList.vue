<script setup>
import { globalStore } from '@/data/store';
import ImageVue from './Image.vue';
import { RecycleScroller, DynamicScroller, DynamicScrollerItem } from 'vue-virtual-scroller'
import { ref, nextTick, reactive, defineExpose, onMounted, watch, computed } from 'vue';

const props = defineProps({
    imageSize: Number,
    height: Number,
    width: Number
})

const imageLines = reactive([])

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
    imageLines.length = 0
    let images = Object.values(globalStore.images)

    let lineWidth = props.width
    let newLine = []
    let actualWidth = 0

    let addLine = (line) => { imageLines.push({ id: imageLines.length, images: line }) }

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

watch(() => props.imageSize, computeLines)

</script>

<template>
    <!-- <div class="d-flex flex-wrap">
        <Image :image="image" v-for="image, index in globalStore.images" :index="index" groupId="0" />
    </div> -->
    <!-- {{ Object.values(globalStore.images) }} -->
    <DynamicScroller :items="imageLines" key-field="id" ref="scroller" :style="'height: '+ props.height +'px;'" :buffer="0"
            :min-item-size="10">
            <template v-slot="{ item, index, active }">
                <DynamicScrollerItem :item="item" :active="active"
                    :data-index="index">
    <div class="d-flex flex-row">
        <ImageVue :image="image" :index="(index * maxPerLine) + i" groupId="0" :size="props.imageSize"
            v-for="image, i in item.images" />
    </div>

    </DynamicScrollerItem>
            </template>
        </DynamicScroller>

    <!-- <RecycleScroller class="" :items="imageLines" :item-size="props.imageSize" key-field="id"
        v-slot="{ item, index, active }">
        <div class="d-flex flex-row">
            <ImageVue :image="image" :index="(index * maxPerLine) + i" groupId="0" :size="props.imageSize"
                v-for="image, i in item.images" />
        </div>
    </RecycleScroller> -->
</template>

<style scoped></style>
