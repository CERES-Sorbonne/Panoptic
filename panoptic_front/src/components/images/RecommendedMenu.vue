<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue';
import ImageRecomended from './ImageRecomended.vue';
import { ImagePropertyValue, Instance, InstancePropertyValue, PropertyMode, PropertyType, PropertyValue } from '@/data/models';
import PropertyValueVue from '../properties/PropertyValue.vue';
import wTT from '../tooltips/withToolTip.vue'
import { Group } from '@/core/GroupManager';
import { useActionStore } from '@/data/actionStore';
import { useDataStore } from '@/data/dataStore';
import { convertSearchGroupResult, sortGroupByScore } from '@/utils/utils';
import ActionSelect from '../actions/ActionSelect.vue';
import { TabManager } from '@/core/TabManager';


interface Sha1Pile {
    sha1: string
    images: Instance[]
}
const data = useDataStore()
const actions = useActionStore()

const props = defineProps<{
    tab: TabManager
    imageSize: number
    group: Group
    width: number
    height: number
}>()

const emits = defineEmits(['scroll', 'close', 'update'])

const maxLines = ref(1)
const lines = reactive([])
const imageMargin = 10

const searchResult = ref<Group>(null)
const propertyValues = reactive([]) as PropertyValue[]

const blacklist = reactive(new Set())

const useFilter = ref(true)

function removeImage(img: Instance) {
    const group = searchResult.value
    if (group.isSha1Group) {
        group.images = group.images.filter(i => i.sha1 != img.sha1)
    } else {
        group.images = group.images.filter(i => i.id != img.id)
    }
    searchResult.value = group
    computeLines()
}

async function acceptRecommend(image: Instance) {
    const imageValues: ImagePropertyValue[] = []
    const instanceValues: InstancePropertyValue[] = []

    propertyValues.forEach(v => {
        if (v.value != undefined) {
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
    await data.setPropertyValues(instanceValues, imageValues)
    removeImage(image)
}

function refuseRecommend(image: Instance) {
    if (searchResult.value.isSha1Group) {
        searchResult.value.images.filter(img => img.sha1 == image.sha1).forEach(img => blacklist.add(img.id))
    } else {
        blacklist.add(image.id)
    }
    removeImage(image)
}

function computeLines() {
    lines.length = 0
    // console.log(props.width, props.imageSize)
    let piles = []
    const images = searchResult.value.images
    if (searchResult.value.isSha1Group) {
        const index = {}
        const sha1s = Array.from(new Set(images.map(i => i.sha1)))
        sha1s.forEach(s => index[s] = [])
        images.forEach(i => index[i.sha1].push(i))
        sha1s.forEach(sha1 => piles.push({ sha1, images: data.sha1Index[sha1] }))
    }
    else {
        images.forEach(img => piles.push({ sha1: img.sha1, images: [img] }))
    }
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
        pile.images = pile.images.filter(i => !blacklist.has(i.id))
        if (pile.images.length == 0) {
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

    if (!actions.hasSimilaryFunction) return
    const func = actions.defaultActions['similar']
    const ctx = actions.getContext(func)
    ctx.instanceIds = props.group.images.map(i => i.id)
    const res = await actions.getSimilarImages(ctx)
    if (!res) return
    if (!res.groups) throw new Error('No instances in ActionResult')

    let groups = convertSearchGroupResult(res.groups, ctx)
    let group = groups[0]

    if (useFilter.value) {
        const valid = new Set(props.tab.collection.filterManager.result.images.map(i => i.id))
        group.images = group.images.filter(i => valid.has(i.id))
    }

    if (group.scores) {
        sortGroupByScore(group)
    }
    searchResult.value = group

    propertyValues.length = 0
    let current = props.group
    while (current) {
        propertyValues.push(...current.meta.propertyValues)
        current = current.parent
    }

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

            <wTT message="main.recommand.close">
                <div class="text-secondary pe-1" @click="emits('close')">
                    <span class="bi bi-x-lg bb"></span>
                </div>
            </wTT>

            <div class="b-left pe-1"></div>

            <wTT message="main.recommand.scroll">
                <div class="text-secondary pe-1" @click="emits('scroll', props.group.id)">
                    <!-- {{ $t('main.recommand.group') }} -->
                    <span class="bi bi-arrow-down-circle bb"></span>
                </div>
            </wTT>

            <div class="b-left pe-1"></div>

            <wTT message="main.recommand.filter">
                <div class="text-secondary pe-1" @click="toggleFilter">
                    <span v-if="useFilter" class="bi bi-funnel-fill bb text-primary"></span>
                    <span v-else class="bi bi-funnel bb"></span>
                </div>
            </wTT>

            <div class="b-left pe-1"></div>

            <wTT message="main.recommand.reload">
                <div class="text-secondary pe-1" @click="getReco">
                    <span class="bi bi-arrow-clockwise bb"></span>
                </div>
            </wTT>

            <div class="b-left pe-1"></div>

            <!-- <div style="border-right: 1px solid black; height: 20px;"></div> -->
            <wTT icon-pos="left" message="main.recommand.tooltip" :icon="true"><span class="text-secondary me-2">{{
                $t('main.recommand.title') }}</span></wTT>
            <div style="padding-top: 2px;" class="me-1">
                <ActionSelect action="similar" @changed="getReco" />
            </div>
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