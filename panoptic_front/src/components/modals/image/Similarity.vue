<script setup lang="ts">
import { Group, GroupManager, SelectedImages } from '@/core/GroupManager';
import { ActionContext, GroupScoreList, Instance } from '@/data/models';
import { computed, onMounted, reactive, ref, watch } from 'vue';
import wTT from '@/components/tooltips/withToolTip.vue'
import TreeScroller from '@/components/scrollers/tree/TreeScroller.vue';
import SelectCircle from '@/components/inputs/SelectCircle.vue';
import { useProjectStore } from '@/data/projectStore';
import { useActionStore } from '@/data/actionStore';
import { useDataStore } from '@/data/dataStore';
import ActionSelect from '@/components/actions/ActionSelect.vue';
import { convertSearchGroupResult, deepCopy, sortGroupByScore } from '@/utils/utils';
import Slider from '@vueform/slider'
const project = useProjectStore()
const actions = useActionStore()
const data = useDataStore()


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


const searchResult = ref<Group>(null)
const scoreInterval = reactive({
    min: 0,
    max: 100,
    maxIsBest: true,
    values: [80, 100],
    description: ''
})

const minSimilarityDist = computed(() => project.getTabManager().state.similarityDist ?? 0.8)


const properties = computed(() => Object.keys(props.visibleProperties).map(k => data.properties[k]))
const defaultFunction = computed(() => actions.defaultActions['similar'])

async function setSimilar() {
    if (!actions.hasSimilaryFunction) return
    // if (modalMode.value != ImageModalMode.Similarity) return
    const ctx: ActionContext = { instanceIds: [props.image.id] }
    const res = await actions.getSimilarImages(ctx)
    console.log(res)
    if (!res.groups) return
    let groups = convertSearchGroupResult(res.groups, ctx)
    let group = groups[0]
    if (group.scores) {
        sortGroupByScore(group)
    }
    searchResult.value = group
    updateInterval(group.scores)
    console.log(group.scores)
    updateSimilarGroup()
}

function updateSimilarGroup() {
    if (!searchResult.value) return

    let group = deepCopy(searchResult.value)
    console.log(scoreInterval.values)
    group.images = group.images.filter(i => group.scores.valueIndex[i.id] >= scoreInterval.values[0] && group.scores.valueIndex[i.id] <= scoreInterval.values[1])

    similarGroup.emptyRoot()
    similarGroup.addCustomGroups(0, [group], true)

    if (scrollerElem.value) {
        scrollerElem.value.computeLines()
        scrollerElem.value.scrollTo('0')
    }
}

function toggleFilter() {
    useFilter.value = !useFilter.value
}

async function updateFunction(name: string) {
    const update = {}
    update['similar'] = name
    await actions.updateDefaultActions(update)
    await setSimilar()
}

function updateInterval(score: GroupScoreList) {
    let minEq = score.min != scoreInterval.min
    let maxEq = score.max != scoreInterval.max
    let bestEq = score.maxIsBest != scoreInterval.maxIsBest

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

onMounted(setSimilar)
watch(() => props.image, setSimilar)
watch(() => scoreInterval.values, updateSimilarGroup)
watch(() => props.width, updateSimilarGroup)
watch(useFilter, updateSimilarGroup)
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
                <div style="margin-left: 6px;" class="me-3">Images Similaires</div>
                <div style="width: 100px;" class="me-3">
                    <Slider v-model=scoreInterval.values :min="0" :max="1" :step="-1" direction="ltr" :merge="0.4"
                        showTooltip="drag" />
                </div>
                <div v-if="scoreInterval.description.length" class="me-1"><wTT :message="scoreInterval.description"><i class="bi bi-info-circle" /></wTT></div>
                <div class="text-secondary">({{ scoreInterval.values[0] }} - {{ scoreInterval.values[1] }})</div>
                <div v-if="similarGroup.hasResult()" class="ms-2 text-secondary">
                    ({{ similarGroup.result.root.children[0].children.length }} images)
                </div>
            </div>
            <div class="d-flex mt-1 mb-1">
                <div class="me-2" style="margin-left: 2px;">Search function</div>
                <div>
                    <ActionSelect :model-value="defaultFunction" :action="'similar'"
                        @update:model-value="updateFunction" />
                </div>
            </div>


            <TreeScroller class="" :image-size="70" :height="props.height - 60" :width="props.width"
                :group-manager="similarGroup" :properties="properties" :hide-options="false" :hide-group="true"
                ref="scrollerElem" :preview="props.preview" />
        </div>
    </template>
</template>