<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue';
import ImageRecomended from './ImageRecomended.vue';
import { ImagePropertyValue, Instance, InstanceMatch, InstancePropertyValue, PropertyMode, PropertyType, PropertyValue } from '@/data/models';
import { useProjectStore } from '@/data/projectStore'
import PropertyValueVue from '../properties/PropertyValue.vue';
import wTT from '../tooltips/withToolTip.vue'
import { Group, UNDEFINED_KEY } from '@/core/GroupManager';
import { useActionStore } from '@/data/actionStore';
import { Exception } from 'sass';
import { useDataStore } from '@/data/dataStore';
interface Sha1Pile {
    sha1: string
    images: Instance[]
}
const project = useProjectStore()
const data = useDataStore()
const actions = useActionStore()

const props = defineProps<{
    imageSize: number
    group: Group
    width: number
    height: number
}>()

const emits = defineEmits(['scroll', 'close', 'update'])

const maxLines = ref(1)
const lines = reactive([])
const imageMargin = 10

const sha1s = reactive([]) as string[]
const propertyValues = reactive([]) as PropertyValue[]

const blacklist = reactive(new Set())

const useFilter = ref(true)

function removeImage(sha1: string) {
    let index = sha1s.indexOf(sha1)
    if (index < 0) {
        return
    }
    sha1s.splice(index, 1)
    computeLines()
}

async function acceptRecommend(image: Instance) {
    const imageValues: ImagePropertyValue[] = []
    const instanceValues: InstancePropertyValue[] = []

    propertyValues.forEach(v => {
        if (v.value != UNDEFINED_KEY) {
            const prop = data.properties[v.propertyId]
            let value = v.value
            if (prop.type == PropertyType.multi_tags) {
                value = image.properties[v.propertyId] ?? []
                value = [...value, v.value]
            }
            else if (prop.type == PropertyType.tag) {
                value = [value]
            }
            if (prop.mode == PropertyMode.id) {
                instanceValues.push({ instanceId: image.id, propertyId: prop.id, value: value })
            } else {
                imageValues.push({ propertyId: prop.id, sha1: image.sha1, value: value })
            }
        }
    })
    await project.setPropertyValues(instanceValues, imageValues)

    removeImage(image.sha1)
}

function refuseRecommend(image: Instance) {
    blacklist.add(image.sha1)
    removeImage(image.sha1)
}

function computeLines() {
    lines.length = 0
    // console.log(props.width, props.imageSize)
    const piles = sha1s.map((sha1: string) => ({ sha1, images: data.sha1Index[sha1] }))
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
        // let img = pile.images[0]
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
    const instanceIds = props.group.images.map(i => i.id)
    let res = await actions.getSimilarImages({ instanceIds })
    console.log(res)
    if (!res.instances) throw new Error('No instances in ActionResult')

    let matches = []
    const scores = res.instances.scores ?? []
    if (res.instances.ids) {
        for (let i in res.instances.ids) {
            const match: InstanceMatch = { id: res.instances.ids[i], score: scores[i] }
            matches.push(match)
        }
    } else {
        for (let i in res.instances.sha1s) {
            const sha1 = res.instances.sha1s[i]
            for (let img of data.sha1Index[sha1]) {
                const match: InstanceMatch = { id: img.id, score: scores[i] }
                matches.push(match)
            }
        }
    }

    matches.sort((a, b) => b.score - a.score)
    if (useFilter.value) {
        const tab = project.getTabManager()
        const valid = new Set(tab.collection.groupManager.result.root.images.map(i => i.id))
        matches = matches.filter(m => valid.has(m.id))
    }
    const resSha1s = Array.from(new Set(matches.map(r => data.instances[r.id].sha1)))

    propertyValues.length = 0
    let current = props.group
    while (current) {
        propertyValues.push(...current.meta.propertyValues)
        current = current.parent
    }
    sha1s.length = 0
    sha1s.push(...resSha1s)

    blacklist.clear()
    computeLines()

    emits('update')
}

function toggleFilter() {
    useFilter.value = !useFilter.value
}

onMounted(getReco)
watch(() => props.group, () => {
    getReco()
    blacklist.clear()
})
watch(() => props.imageSize, computeLines)
watch(() => props.width, computeLines)
watch(useFilter, getReco)

</script>

<template>
    <div class="reco-container">
        <div class="d-flex flex-row m-0 ps-2 center mb-1 mt-0" style="height: 25px;">

            <div class="text-secondary pe-1" @click="emits('close')">
                <span class="bi bi-x-lg bb " style=""></span>
            </div>

            <div class="b-left pe-1"></div>

            <div class="text-secondary pe-1" @click="emits('scroll', props.group.id)">
                <!-- {{ $t('main.recommand.group') }} -->
                <span class="bi bi-arrow-down-circle bb"></span>
            </div>

            <div class="b-left pe-1"></div>

            <div class="text-secondary pe-1" @click="toggleFilter">
                <span v-if="useFilter" class="bi bi-funnel-fill bb text-primary"></span>
                <span v-else class="bi bi-funnel bb"></span>
            </div>

            <div class="b-left pe-1"></div>

            <!-- <div style="border-right: 1px solid black; height: 20px;"></div> -->

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
    /* border-right: 2px solid var(--border-color);
    border-bottom: 2px solid var(--border-color);
    border-left: 2px solid var(--border-color); */
    font-size: 14px;
    /* height: 20px; */
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

.b-left {
    border-left: 1px solid var(--border-color);
    height: 80%;
}

.center {
    display: flex;
    justify-content: center;
    /* Horizontal centering */
    align-items: center;
    /* Vertical centering */
}
</style>