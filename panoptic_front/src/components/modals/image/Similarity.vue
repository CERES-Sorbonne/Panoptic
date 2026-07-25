<script setup lang="ts">
// Similarity results panel.
//
// This is a flat, pre-ordered, throwaway list — no grouping, no sorting state, no clustering.
// So it holds no GroupManager: the state is a plain instance array plus a per-slot score map,
// rendered by the groupless ImageScroller. (It used to build a one-root GroupManager tree and
// push it in with setAsRoot, which meant every read of that non-reactive tree needed the
// version/emit contract to be observed by hand.)
import { ActionResult, Instance, ScoreInterval } from '@/data/models';
import { SelectedImages } from '@/core/GroupManager';
import { useColumnStore } from '@/data/columnStore';
import { computed, markRaw, nextTick, onMounted, Reactive, reactive, ref, shallowRef, watch } from 'vue';
import { watchDebounced } from '@vueuse/core';
import wTT from '@/components/tooltips/withToolTip.vue'
import ImageScroller from '@/components/scrollers/image/ImageScroller.vue';
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
    visibleProperties: { [id: number]: boolean }
    preview: SelectedImages
}>()

const emits = defineEmits<{
    // Every instance id currently in the result (piles expanded), so the modal can paint /
    // preview the whole set. Emitted on every recompute.
    (e: 'update:instances', ids: number[]): void
    (e: 'open', instance: Instance): void
}>()

const useFilter = ref(false)
const scrollerElem = ref(null)

let _updatePending = false
function scheduleUpdate() {
    if (_updatePending) return
    _updatePending = true
    nextTick(async () => {
        _updatePending = false
        await updateResults()
    })
}

// Raw search state kept in column-store *slot* space so filtering/sorting
// never has to go slot -> instanceId -> score. `searchSlots` is sorted by
// score; `slotScore` maps a slot directly to its raw score.
let searchSlots: number[] = []
const slotScore = markRaw(new Map<number, number>())
let scoreMeta: ScoreMeta | null = null
const hasResult = ref(false)

// What the scroller renders: one cell per sha1 (the results are sha1-based, so several
// instances of the same image collapse into one cell, as the tree scroller's piles did).
const instances = shallowRef<Instance[]>([])
const scores = shallowRef<Record<number, number>>({})
const piles = shallowRef<Record<number, number[]>>({})
const allIds = shallowRef<number[]>([])

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

function updateResults() {
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

    // Collapse to one cell per sha1, keeping the (score-ordered) first slot as the
    // representative. `piles` carries the instances each cell stands for, so selecting a
    // cell selects them all and the count badge shows how many.
    const col = useColumnStore()
    const ids = col.instanceIds()
    const sha1s = col.sha1s()
    const list: Instance[] = []
    const nextScores: Record<number, number> = {}
    const nextPiles: Record<number, number[]> = {}
    const every: number[] = []
    const repBySha1 = new Map<string, number>()

    for (const slot of slots) {
        const id = ids[slot]
        if (id === undefined) continue
        every.push(id)
        const sha1 = sha1s[slot]
        const rep = sha1 != null ? repBySha1.get(sha1) : undefined
        if (rep !== undefined) {
            nextPiles[rep].push(id)
            continue
        }
        if (sha1 != null) repBySha1.set(sha1, id)
        nextPiles[id] = [id]
        list.push({ id, imageUrl: data.baseImgUrl + 'by_size/' + sha1 })
        const score = slotScore.get(slot)
        if (score !== undefined) nextScores[id] = formatScore(score)
    }

    instances.value = list
    scores.value = nextScores
    piles.value = nextPiles
    allIds.value = every
    emits('update:instances', every)

    // The list is score-ordered, so any recompute changes what "best match" means — go back
    // to the top rather than leaving the user parked mid-list.
    nextTick(() => scrollerElem.value?.scrollToTop())
}

// Scores come in whatever scale the similarity function uses — 0..1 for a cosine distance,
// 0..100 for a percentage. Rounding to an integer is only right for the wide ranges, so the
// number of decimals follows the range the backend reported.
function formatScore(score: number): number {
    const range = scoreMeta ? scoreMeta.max - scoreMeta.min : 0
    const decimals = range >= 100 ? 0 : range >= 10 ? 1 : 2
    return Number(score.toFixed(decimals))
}

function toggleFilter() {
    useFilter.value = !useFilter.value
}

// ── Select all ──────────────────────────────────────────────────────────────
// The panel selects in the global namespace (as the similarity GroupManager did), so the
// modal's paint/stamp actions keep seeing the same selection.
const col = useColumnStore()
const allSelected = computed(() => {
    col.selectionTick()
    const ids = allIds.value
    return ids.length > 0 && ids.every(id => col.isSelectedId(id))
})

function toggleAll() {
    if (allSelected.value) col.deselectIds(allIds.value)
    else col.selectIds(allIds.value)
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
                <SelectCircle v-if="allIds.length" :model-value="allSelected" @update:model-value="v => toggleAll()"
                    style="margin-top: -1px;" />
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
                <div class="text-secondary">({{ formatScore(scoreInterval.values[0]) }} - {{
                    formatScore(scoreInterval.values[1]) }})</div>
                <div v-if="instances.length" class="ms-2 text-secondary">
                    ({{ instances.length }} images)
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

            <ImageScroller input-key="similarity-tree" :image-size="project.uiState.similarityImageSize"
                :height="props.height - 45" :width="props.width - 45" :instances="instances"
                :properties="properties" :scores="scores" :piles="piles" :preview="props.preview" :no-drag="true"
                ref="scrollerElem" @open="i => emits('open', i)" />
        </div>
    </template>
</template>
