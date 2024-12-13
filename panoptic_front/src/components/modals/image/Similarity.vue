<script setup lang="ts">
import { GroupManager, SelectedImages } from '@/core/GroupManager';
import { Instance, InstanceMatch, SearchResult } from '@/data/models';
import { computed, onMounted, reactive, ref, watch } from 'vue';
import wTT from '@/components/tooltips/withToolTip.vue'
import TreeScroller from '@/components/scrollers/tree/TreeScroller.vue';
import RangeInput from '@/components/inputs/RangeInput.vue';
import SelectCircle from '@/components/inputs/SelectCircle.vue';
import { useProjectStore } from '@/data/projectStore';
import { useActionStore } from '@/data/actionStore';
import { useDataStore } from '@/data/dataStore';
import ActionSelect from '@/components/actions/ActionSelect.vue';
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
const search = ref<SearchResult>(null)
const minSimilarityDist = computed(() => project.getTabManager().state.similarityDist ?? 0.8)
const state = reactive({
    sha1Scores: {}
})

const properties = computed(() => Object.keys(props.visibleProperties).map(k => data.properties[k]))
const defaultFunction = computed(() => actions.defaultActions['similar'])

async function setSimilar() {
    if (!actions.hasSimilaryFunction) return
    // if (modalMode.value != ImageModalMode.Similarity) return
    const res = await actions.getSimilarImages({ instanceIds: [props.image.id] })
    if (!res.instances) return

    let matches: InstanceMatch[] = []
    const scores = res.instances.scores ?? []
    if (res.instances.ids) {
        for (let i in res.instances.ids) {
            const match: InstanceMatch = { id: res.instances.ids[i], score: scores[i] ?? 1.0 }
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
    search.value = { matches }
    updateSimilarGroup()
}

function updateSimilarGroup() {
    if (!search.value) return

    let matches = search.value.matches.filter(i => i.score >= (minSimilarityDist.value))

    if (useFilter.value) {
        const tab = project.getTabManager()
        const valid = new Set(tab.collection.filterManager.result.images.map(i => i.id))
        matches = matches.filter(m => valid.has(m.id))
    }

    const images = matches.map(m => data.instances[m.id])
    state.sha1Scores = {}
    matches.forEach(m => state.sha1Scores[data.instances[m.id].sha1] = m.score)
    images.sort((a, b) => state.sha1Scores[b.sha1] - state.sha1Scores[a.sha1])

    similarGroup.group(images, undefined, true)

    if (scrollerElem.value) {
        scrollerElem.value.computeLines()
        scrollerElem.value.scrollTo('0')
    }

}

function setSimilarDist(value: number) {
    project.getTabManager().state.similarityDist = value
    similarGroup.clearSelection()
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

onMounted(setSimilar)
watch(() => props.image, setSimilar)
watch(minSimilarityDist, updateSimilarGroup)
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
                <wTT message="modals.image.similarity_filter_tooltip">
                    <RangeInput class="me-2" :min="0" :max="1" :model-value="minSimilarityDist"
                        @update:model-value="setSimilarDist" />
                </wTT>
                <div>min: {{ minSimilarityDist }} </div>
                <div v-if="similarGroup.hasResult()" class="ms-2 text-secondary">
                    ({{ similarGroup.result.root.children.length }} images)
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
                :sha1-scores="state.sha1Scores" ref="scrollerElem" :preview="props.preview" />
        </div>
    </template>
</template>