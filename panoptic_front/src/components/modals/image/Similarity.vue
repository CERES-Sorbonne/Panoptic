<script setup lang="ts">
import { GroupManager, GroupType, SelectedImages, buildGroup } from '@/core/GroupManager';
import { ActionResult, Instance, ScoreInterval } from '@/data/models';
import { useColumnStore } from '@/data/columnStore';
import { computed, markRaw, nextTick, onMounted, Reactive, reactive, ref, watch } from 'vue';
import { watchDebounced } from '@vueuse/core';
import wTT from '@/components/tooltips/withToolTip.vue'
import TreeScroller from '@/components/scrollers/tree/TreeScroller.vue';
import SelectCircle from '@/components/inputs/SelectCircle.vue';
import { useActionStore } from '@/data/actionStore';
import { useDataStore } from '@/data/dataStore';
import Slider from '@vueform/slider'
import { useProjectStore } from '@/data/projectStore';
import { useTabStore } from '@/data/tabStore';
import RangeInput from '@/components/inputs/RangeInput.vue';
import ActionButton2 from '@/components/actions/ActionButton2.vue';
const actions = useActionStore()
const data = useDataStore()
const project = useProjectStore()
const tabStore = useTabStore()

type ScoreMeta = { min: number, max: number, maxIsBest: boolean, description: string }

const props = defineProps<{
    image: Instance
    width: number
    height: number
    similarGroup?: GroupManager
    visibleProperties: { [id: number]: boolean }
    preview: SelectedImages
}>()
const similarGroup = props.similarGroup ?? new GroupManager()
similarGroup.setSha1Mode(true)

const useFilter = ref(false)
const scrollerElem = ref(null)

let _updatePending = false
function scheduleUpdate() {
    if (_updatePending) return
    _updatePending = true
    nextTick(async () => {
        _updatePending = false
        await updateSimilarGroup()
    })
}

// Raw search state kept in column-store *slot* space so filtering/sorting
// never has to go slot -> instanceId -> score. `searchSlots` is sorted by
// score; `slotScore` maps a slot directly to its raw score.
let searchSlots: number[] = []
const slotScore = markRaw(new Map<number, number>())
let scoreMeta: ScoreMeta | null = null
const hasResult = ref(false)

const scoreInterval: Reactive<ScoreInterval> = reactive({
    min: 0,
    max: 100,
    maxIsBest: true,
    values: [80, 100],
    description: ''
})

const properties = computed(() => Object.keys(props.visibleProperties).map(k => data.properties[k]))

// Build the slot list + per-slot scores from a raw search result. The sha1
// path does a single pass over the column-store arrays (O(slotCount)) instead
// of one full scan per sha1 (getInstancesBySha1), so it scales to far larger
// result sets.
function processResult(res: ActionResult) {
    if (!res || !res.groups || !res.groups.length) return
    const col = useColumnStore()
    const group = res.groups[0]
    const hasScores = !!group.scores

    slotScore.clear()
    const slots: number[] = []

    if (group.ids) {
        const ids = group.ids
        for (let i = 0; i < ids.length; i++) {
            const s = col.slotMap.get(ids[i])
            if (s === undefined) continue
            slots.push(s)
            if (hasScores) slotScore.set(s, group.scores.values[i])
        }
    } else {
        const resultSha1s = group.sha1s ?? []
        const sha1ToScore = new Map<string, number>()
        for (let i = 0; i < resultSha1s.length; i++) {
            sha1ToScore.set(resultSha1s[i], hasScores ? group.scores.values[i] : 0)
        }
        const allSha1 = col.sha1s()
        const deleted = col.deletedMask()
        const n = col.slotCount()
        for (let s = 0; s < n; s++) {
            if (deleted[s]) continue
            const sha1 = allSha1[s]
            if (sha1 === null) continue
            const score = sha1ToScore.get(sha1)
            if (score === undefined) continue
            slots.push(s)
            if (hasScores) slotScore.set(s, score)
        }
    }

    if (hasScores) {
        const dir = group.scores.maxIsBest ? -1 : 1
        slots.sort((a, b) => (slotScore.get(a) - slotScore.get(b)) * dir)
        scoreMeta = {
            min: group.scores.min,
            max: group.scores.max,
            maxIsBest: group.scores.maxIsBest,
            description: group.scores.description
        }
    } else {
        scoreMeta = null
    }

    searchSlots = slots
    hasResult.value = true

    setDefaultInterval()
    if (scoreMeta) updateInterval(scoreMeta)
    scheduleUpdate()
}

async function setSimilar() {
    if (!actions.hasSimilaryFunction) return
    const func = actions.defaultActions['similar']
    const ctx = actions.getContext(func)
    ctx.instanceIds = [props.image.id]
    const res = await actions.getSimilarImages(ctx)
    processResult(res)
}

async function importSimilar(res: ActionResult) {
    processResult(res)
}

async function updateSimilarGroup() {
    if (!hasResult.value) return

    let slots = searchSlots

    if (useFilter.value) {
        const validSlots = new Set(tabStore.getMainTab().collection.filterManager.result.slots)
        slots = slots.filter(s => validSlots.has(s))
    }

    if (scoreMeta) {
        const lo = scoreInterval.values[0]
        const hi = scoreInterval.values[1]
        slots = slots.filter(s => {
            const score = slotScore.get(s)
            return score >= lo && score <= hi
        })
    }

    // `slots` may still be a reference to `searchSlots` when no filter ran;
    // setAsRoot copies it, so that's safe.
    await similarGroup.setAsRoot(buildGroup(0, slots, GroupType.Cluster))

    if (scrollerElem.value) {
        scrollerElem.value.computeLines()
        scrollerElem.value.scrollTo('0')
    }
}

function toggleFilter() {
    useFilter.value = !useFilter.value
}

function updateInterval(score: ScoreMeta) {
    let minEq = score.min === scoreInterval.min
    let maxEq = score.max === scoreInterval.max
    let bestEq = score.maxIsBest === scoreInterval.maxIsBest

    if (minEq && maxEq && bestEq) return

    scoreInterval.min = score.min
    scoreInterval.max = score.max
    scoreInterval.maxIsBest = score.maxIsBest
    scoreInterval.description = score.description

    let v0 = scoreInterval.values[0]
    let v1 = scoreInterval.values[1]

    if (v0 > score.max || v0 < score.min) {
        if (scoreInterval.maxIsBest) {
            v0 = (score.max + score.min) / 2
        } else {
            v0 = scoreInterval.min
        }
    }
    if (v1 > score.max || v1 < score.min) {
        if (scoreInterval.maxIsBest) {
            v1 = scoreInterval.max
        } else {
            v1 = (score.max + score.min) / 2
        }
    }
    scoreInterval.values = [v0, v1]
}

function setDefaultInterval() {
    const intervals = project.uiState.similarityIntervals
    const func = actions.defaultActions['similar']
    if (!func || !intervals[func.id]) {
        return
    }
    Object.assign(scoreInterval, intervals[func.id])
}

setDefaultInterval()

onMounted(setSimilar)
watch(() => props.image, setSimilar)
watch(() => scoreInterval.values, scheduleUpdate)
watch(() => props.width, scheduleUpdate)
watch(useFilter, scheduleUpdate)
watch(scoreInterval, () => {
    project.updateScoreInterval(actions.defaultActions['similar'].id, scoreInterval)
})
watchDebounced(() => project.uiState.similarityImageSize, () => project.saveUiState(), { debounce: 400 })
</script>

<template>
    <div v-if="!actions.hasSimilaryFunction" class="ps-2">No Similary Function found.</div>
    <template v-else>
        <div class="bg-white">
            <div class="d-flex mb-1 flex-center" style="height: 25px;">
                <SelectCircle v-if="similarGroup.hasResult()" :model-value="similarGroup.result.root.view.selected"
                    @update:model-value="v => similarGroup.toggleAll()" style="margin-top: -1px;" />
                <div class="sep ms-1 me-1"></div>
                <wTT message="modals.image.main_filter_tooltip">
                    <div class="text-secondary" @click="toggleFilter">
                        <span v-if="useFilter" class="bi bi-funnel-fill bb text-primary"></span>
                        <span v-else class="bi bi-funnel bb"></span>
                    </div>
                </wTT>
                <div class="sep ms-1 me-1"></div>
                <div style="margin-left: 6px;" class="me-3">
                    <ActionButton2 action="similar" @call="importSimilar" :images="[props.image]">
                        <span>
                            <i class="bi bi-boxes me-1" />Images similaire
                        </span>
                    </ActionButton2>
                </div>
                <div style="width: 100px;" class="me-3">
                    <Slider v-model=scoreInterval.values :min="scoreInterval.min" :max="scoreInterval.max" :step="-1"
                        direction="ltr" :merge="0.4" showTooltip="drag" />
                </div>
                <div v-if="scoreInterval.description.length" class="me-1">
                    <wTT :message="scoreInterval.description"><i class="bi bi-info-circle" /></wTT>
                </div>
                <div class="text-secondary">({{ scoreInterval.values[0] }} - {{ scoreInterval.values[1] }})</div>
                <div v-if="similarGroup.hasResult()" class="ms-2 text-secondary">
                    ({{ similarGroup.result.root.children.length }} images)
                </div>
                <div class="d-flex ms-3">
                    <wTT message="main.menu.image_size_tooltip" :click="false">
                        <div class="bi bi-aspect-ratio me-1"></div>
                    </wTT>
                    <div>
                        <RangeInput :min="60" :max="250" v-model="project.uiState.similarityImageSize" />
                    </div>
                </div>
            </div>


            <TreeScroller input-key="similarity-tree" class="" :image-size="project.uiState.similarityImageSize"
                :height="props.height - 45" :width="props.width - 45" :group-manager="similarGroup"
                :properties="properties" :hide-options="false" :hide-group="true" ref="scrollerElem"
                :preview="props.preview" />
        </div>
    </template>
</template>