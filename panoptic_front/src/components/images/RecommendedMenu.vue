<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue';
import ImageVue from './Image.vue';
import ImageRecomended from './ImageRecomended.vue';
import { Group, GroupIndex, Image, PropertyType, PropertyValue, Recommendation } from '@/data/models';
import { globalStore } from '@/data/store';
import PropertyValueVue from '../properties/PropertyValue.vue';
import { right } from '@popperjs/core';
import { UNDEFINED_KEY } from '@/utils/groups';


const props = defineProps({
    imageSize: Number,
    reco: Object as () => Recommendation,
    width: Number,
    height: Number
})

const emits = defineEmits(['scroll', 'close'])

const maxLines = ref(1)
const lines = reactive([])
const imageMargin = 10

const blacklist = reactive(new Set())

function removeImage(sha1: string) {
    let index = props.reco.images.indexOf(sha1)
    if(index < 0) {
        return
    }
    props.reco.images.splice(index, 1)
    computeLines()
}

function acceptRecommend(image: Image) {
    props.reco.values.forEach(v => {
        if(v.value != UNDEFINED_KEY) {
            globalStore.setPropertyValue(v.propertyId, image, v.value)
        }
    })
    removeImage(image.sha1)
}

function refuseRecommend(image: Image) {
    blacklist.add(image.sha1)
    removeImage(image.sha1)
}

function computeLines() {
    lines.length = 0
    // console.log(props.width, props.imageSize)
    const images = globalStore.getOneImagePerSha1(props.reco.images)
    computeImageLines(images, lines, maxLines.value, props.imageSize, props.width)
}

function computeImageLines(images: Image[], lines: Image[][], maxLines: number, imageWidth: number, totalWidth: number) {
    let lineWidth = totalWidth
    let newLine: Image[] = []
    let actualWidth = 0

    for (let i = 0; i < images.length; i++) {
        if (lines.length >= maxLines) {
            break
        }
        let img = images[i]
        if(blacklist.has(img.sha1)) {
            continue
        }
        let imgWidth = imageWidth + imageMargin
        if (actualWidth + imgWidth < lineWidth) {
            newLine.push(img)
            actualWidth += imgWidth
            continue
        }
        if (newLine.length == 0) {
            throw 'Images seems to be to big for the line'
        }
        lines.push(newLine)
        if (lines.length < maxLines) {
            newLine = [img]
            actualWidth = imgWidth
        }
    }

    if(newLine.length > 0 && lines.length < maxLines) {
        lines.push(newLine)
    }
}

onMounted(computeLines)
watch(() => props.reco.images, computeLines, { deep: true })
watch(() => props.imageSize, computeLines)
watch(() => props.width, computeLines)
watch(() => props.reco.groupId, (newValue, oldValue) => {
    if(oldValue != newValue) {
        blacklist.clear()
        // console.log('clear')
    }
}, {deep: true})

</script>

<template>
    <div class="reco-container">
        <div class="d-flex flex-row m-0 ps-2 pb-2">
            <span class="text-secondary me-2">Images recommandées</span>
            <div class="flex-grow-1">
                <div class="d-flex flex-row">
                    <template v-for="value, index in props.reco.values">
                        <PropertyValueVue class="" :value="value" />
                        <span v-if="index < props.reco.values.length - 1" class="ms-1 me-1" style=""><i class="bi bi-chevron-right text-secondary"></i></span>
                    </template>
                </div>
            </div>
            <span class="text-secondary scroll ps-1 pe-1 clickable" @click="emits('scroll', props.reco.groupId)">Voir Groupe</span>
            <span class="text-secondary me-1 close  ps-1 pe-1 clickable" @click="emits('close')"><i class="bi bi-x"></i></span>
        </div>
        <div :style="'margin-left:' + imageMargin + 'px;'">
            <div v-for="line in lines">
                <div class="d-flex flex-row">
                    <ImageRecomended :image="image" :size="props.imageSize" v-for="image in line" @accept="acceptRecommend"
                        @refuse="refuseRecommend" :style="'margin-right:' + imageMargin + 'px;'" />
                </div>
            </div>
        </div>

    </div>
</template>

<style scoped>
.close {
    border-right: 2px solid var(--border-color);
    border-bottom: 2px solid var(--border-color);
    border-left: 2px solid var(--border-color);
    font-size: 14px;
}

.scroll {
    border-bottom: 2px solid var(--border-color);
    border-left: 2px solid var(--border-color);
    font-size: 13px;
}

.reco-container {
    margin-top: 0;
    border-bottom: 1px solid var(--border-color);
    border-top: 1px solid var(--border-color);
    padding: 0px;
    padding-bottom: 10px;
}

.image-line {
    height: 100%;
    border-left: 1px solid var(--border-color);
    padding-left: 10px;
}

.active {
    border-left: 1px solid blue;
}
</style>