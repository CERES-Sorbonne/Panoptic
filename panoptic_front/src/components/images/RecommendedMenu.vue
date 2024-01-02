<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue';
import ImageRecomended from './ImageRecomended.vue';
import { Image, PropertyType, PropertyValue, Recommendation } from '@/data/models';
import { useProjectStore } from '@/data/projectStore'
import PropertyValueVue from '../properties/PropertyValue.vue';
import wTT from '../tooltips/withToolTip.vue'
import { Group, UNDEFINED_KEY } from '@/core/GroupManager';
import { getSimilarImages } from '@/utils/utils';
interface Sha1Pile {
    sha1: string
    images: Image[]
}
const store = useProjectStore()
const props = defineProps({
    imageSize: Number,
    group: Object as () => Group,
    width: Number,
    height: Number,
})

const emits = defineEmits(['scroll', 'close', 'update'])

const maxLines = ref(1)
const lines = reactive([])
const imageMargin = 10

const sha1s = reactive([]) as string[]
const propertyValues = reactive([]) as PropertyValue[]

const blacklist = reactive(new Set())

function removeImage(sha1: string) {
    let index = sha1s.indexOf(sha1)
    if (index < 0) {
        return
    }
    sha1s.splice(index, 1)
    computeLines()
}

function acceptRecommend(image: Image) {
    propertyValues.forEach(v => {
        if (v.value != UNDEFINED_KEY) {
            let mode = store.data.properties[v.propertyId].type == PropertyType.multi_tags ? 'add' : null
            store.setPropertyValue(v.propertyId, image, v.value, mode)
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
    const piles = sha1s.map((sha1: string) => ({ sha1, images: store.data.sha1Index[sha1] }))
    computeImageLines(piles, lines, maxLines.value, props.imageSize, props.width)
}

function computeImageLines(piles: Sha1Pile[], lines: Sha1Pile[][], maxLines: number, imageWidth: number, totalWidth: number) {
    let lineWidth = totalWidth
    let newLine: Sha1Pile[] = []
    let actualWidth = 0

    for (let i = 0; i < piles.length; i++) {
        if (lines.length >= maxLines) {
            break
        }
        let pile = piles[i]
        let img = pile.images[0]
        if (blacklist.has(pile.sha1)) {
            continue
        }
        let imgWidth = imageWidth + imageMargin
        if (actualWidth + imgWidth < lineWidth) {
            newLine.push(pile)
            actualWidth += imgWidth
            continue
        }
        if (newLine.length == 0) {
            throw new Error('Images seems to be to big for the line')
        }
        lines.push(newLine)
        if (lines.length < maxLines) {
            newLine = [pile]
            actualWidth = imgWidth
        }
    }

    if (newLine.length > 0 && lines.length < maxLines) {
        lines.push(newLine)
    }
}

async function getReco() {
    if (!props.group) return
    console.log('get reco')
    const requestSha1s = props.group.images.map(i => i.sha1)
    let res = await getSimilarImages(requestSha1s) as any[]
    const resSha1s = res.map(r => r.sha1)

    propertyValues.length = 0
    let current = props.group
    while (current) {
        propertyValues.push(...current.meta.propertyValues)
        current = current.parent
    }
    sha1s.length = 0
    sha1s.push(...resSha1s)

    computeLines()
    blacklist.clear()

    emits('update')
}

onMounted(getReco)
watch(() => props.group, () => {
    getReco()
    blacklist.clear()
})
watch(() => props.imageSize, computeLines)
watch(() => props.width, computeLines)

</script>

<template>
    <div class="reco-container">
        <div class="d-flex flex-row m-0 ps-2 pb-2">
            <wTT icon-pos="left" message="main.recommand.tooltip" :icon="true"><span class="text-secondary me-2">{{
                $t('main.recommand.title') }}</span></wTT>
            <div class="flex-grow-1">
                <div class="d-flex flex-row">
                    <template v-for="value, index in propertyValues">
                        <PropertyValueVue class="" :value="value" />
                        <div v-if="index < propertyValues.length - 1" class="separator"></div>
                    </template>
                </div>
            </div>
            <span class="text-secondary scroll ps-1 pe-1 clickable" @click="emits('scroll', props.group.id)">{{
                $t('main.recommand.group') }}</span>
            <span class="text-secondary me-1 close  ps-1 pe-1 clickable" @click="emits('close')"><i
                    class="bi bi-x"></i></span>
        </div>
        <div :style="'margin-left:' + imageMargin + 'px;'">
            <div v-for="line in lines">
                <div class="d-flex flex-row">
                    <ImageRecomended :pile="pile" :size="props.imageSize" v-for="pile in line" @accept="acceptRecommend"
                        @refuse="refuseRecommend" :style="'margin-right:' + imageMargin + 'px;'" />
                </div>
            </div>
        </div>

    </div>
</template>

<style scoped>
.separator {
    border-left: 2px solid var(--border-color);
    margin: 3px 4px;
}

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