<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue';
import ImageVue from './Image.vue';
import ImageRecomended from './ImageRecomended.vue';
import { Group, GroupIndex, Image, PropertyType, PropertyValue, Recommendation } from '@/data/models';
import { globalStore } from '@/data/store';


const props = defineProps({
    imageSize: Number,
    reco: Object as () => Recommendation,
    width: Number,
    height: Number,
    propertyValues: Array<PropertyValue>
})

const emits = defineEmits(['hover', 'unhover', 'scroll', 'update', 'close'])
//:style="'padding-left:' + (props.item.depth * MARGIN) + 'px'"

const maxLines = ref(1)
const lines = reactive([])

function acceptRecommend(image: Image) {
    // let group = props.index[props.item.groupId]
    // let index = group.allSimilarSha1s.indexOf(image.sha1)
    // if (index < 0) {
    //     return
    // }

    // let property = globalStore.properties[group.propertyId]
    // let type = property.type

    // let propertyValue: string | string[] | number[] = group.name
    // if (type == PropertyType.tag || type == PropertyType.multi_tags) {
    //     propertyValue = [Number(propertyValue)]
    // }

    // globalStore.addOrUpdatePropertyToImage(image.id, property.id, propertyValue)


    // group.allSimilarSha1s.splice(index, 1)
    // emits('update', props.item.groupId)
}

function refuseRecommend(image: Image) {
    // let group = props.index[props.item.groupId]
    // let index = group.allSimilarSha1s.indexOf(image.sha1)
    // if (index < 0) {
    //     return
    // }

    // group.allSimilarSha1s.splice(index, 1)
    // group.similarSha1sBlacklist.push(image.sha1)
    // emits('update', props.item.groupId)
}

function computeLines() {
    lines.length = 0
    console.log(props.width, props.imageSize)
    const images = globalStore.getOneImagePerSha1(props.reco.images)
    computeImageLines(images, lines, maxLines.value, props.imageSize, props.width)
}

function computeImageLines(images: Image[], lines: Image[][], maxLines: number, imageHeight: number, totalWidth: number) {
    let lineWidth = totalWidth
    let newLine = []
    let actualWidth = 20

    for (let i = 0; i < images.length; i++) {
        if (lines.length >= maxLines) {
            break
        }
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
        lines.push(newLine)
        newLine = []
        actualWidth = 0
    }

    if (newLine.length > 0) {
        lines.push(newLine)
    }
    // emits('update')
}

onMounted(computeLines)
watch(() => props.reco.images, computeLines, {deep: true})
watch(() => props.imageSize, computeLines)

</script>

<template>
    <div class="reco-container">
        <div class="d-flex flex-row m-0 ps-2 pb-1">
            <span class="text-secondary flex-grow-1">Images recommandées</span>
            <span class="text-secondary scroll ps-1 pe-1">Voir Groupe</span>
            <span class="text-secondary me-1 close  ps-1 pe-1" @click="emits('close')"><i class="bi bi-x"></i></span>
        </div>
        <div v-for="line in lines">
            <div class="d-flex flex-row ps-2">
                <ImageRecomended :image="image" :size="props.imageSize" v-for="image in line" @accept="acceptRecommend"
                    @refuse="refuseRecommend" />
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