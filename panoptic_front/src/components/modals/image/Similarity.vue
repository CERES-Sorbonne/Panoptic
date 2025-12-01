<script setup lang="ts">
import { Group, GroupManager, SelectedImages } from '@/core/GroupManager';
import { ActionResult, GroupScoreList, Instance, ScoreInterval } from '@/data/models';
import { computed, onMounted, Reactive, reactive, ref, shallowRef, watch } from 'vue';
import wTT from '@/components/tooltips/withToolTip.vue'
import TreeScroller from '@/components/scrollers/tree/TreeScroller.vue';
import SelectCircle from '@/components/inputs/SelectCircle.vue';
import { useActionStore } from '@/data/actionStore';
import { useDataStore } from '@/data/dataStore';
import ActionSelect from '@/components/actions/ActionSelect.vue';
import { convertSearchGroupResult, deepCopy, sortGroupByScore } from '@/utils/utils';
import Slider from '@vueform/slider'
import { useProjectStore } from '@/data/projectStore';
import { useTabStore } from '@/data/tabStore';
import RangeInput from '@/components/inputs/RangeInput.vue';
import ActionButton2 from '@/components/actions/ActionButton2.vue';
const actions = useActionStore()
const data = useDataStore()
const project = useProjectStore()
const tabStore = useTabStore()

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

const useFilter = ref(true)
const scrollerElem = ref(null)

const searchResult = shallowRef<Group>(null)
const scoreInterval: Reactive<ScoreInterval> = reactive({
    min: 0,
    max: 100,
    maxIsBest: true,
    values: [80, 100],
    description: ''
})

const properties = computed(() => Object.keys(props.visibleProperties).map(k => data.properties[k]))

async function setSimilar() {
    if (!actions.hasSimilaryFunction) return
    const func = actions.defaultActions['similar']
    const ctx = actions.getContext(func)
    console.log(ctx.uiInputs)
    ctx.instanceIds = [props.image.id]
    const res = await actions.getSimilarImages(ctx)
    if (!res || !res.groups) return
    let groups = convertSearchGroupResult(res.groups)
    let group = groups[0]
    if (group.scores) {
        sortGroupByScore(group)
    }
    searchResult.value = group
    setDefaultInterval()
    updateInterval(group.scores)
    updateSimilarGroup()
}

async function importSimilar(res: ActionResult) {
    if (!res || !res.groups) return
    let groups = convertSearchGroupResult(res.groups)
    let group = groups[0]
    if (group.scores) {
        sortGroupByScore(group)
    }
    searchResult.value = group
    setDefaultInterval()
    updateInterval(group.scores)
    updateSimilarGroup()
}

function updateSimilarGroup() {
    if (!searchResult.value) return
    console.log('update')
    let group = { ...searchResult.value }
    if (useFilter.value) {
        let valid = {}
        tabStore.getMainTab().collection.filterManager.result.images.forEach(i => valid[i.id] = true)
        group.images = group.images.filter(i => valid[i.id])
    }
    group.images = group.images.filter(i => group.scores.valueIndex[i.id] >= scoreInterval.values[0] && group.scores.valueIndex[i.id] <= scoreInterval.values[1])

    similarGroup.setAsRoot(group)

    if (scrollerElem.value) {
        scrollerElem.value.computeLines()
        scrollerElem.value.scrollTo('0')
    }
}

function toggleFilter() {
    useFilter.value = !useFilter.value
}

function updateInterval(score: GroupScoreList) {
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
watch(() => scoreInterval.values, updateSimilarGroup)
watch(() => props.width, updateSimilarGroup)
watch(useFilter, updateSimilarGroup)
watch(scoreInterval, () => {
    project.updateScoreInterval(actions.defaultActions['similar'].id, scoreInterval)
})
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
                <div style="margin-left: 6px;" class="me-3 sbb">
                    <ActionButton2 action="similar" @call="importSimilar" :images="[props.image]">
                        <span>
                            <i class="bi bi-plugin" />Images similaire
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