<script setup lang="ts">
import { GroupManager } from '@/core/GroupManager';
import { Image, SearchResult } from '@/data/models';
import { computed, onMounted, reactive, ref, watch } from 'vue';
import wTT from '@/components/tooltips/withToolTip.vue'
import TreeScroller from '@/components/scrollers/tree/TreeScroller.vue';
import RangeInput from '@/components/inputs/RangeInput.vue';
import SelectCircle from '@/components/inputs/SelectCircle.vue';
import { useProjectStore } from '@/data/projectStore';
import { apiGetSimilarImages } from '@/data/api';
const project = useProjectStore()

const props = defineProps<{
    image: Image
    width: number
    height: number
    similarGroup?: GroupManager
    visibleProperties: { [id: number]: boolean }
}>()
const similarGroup = props.similarGroup ?? new GroupManager()
similarGroup.setSha1Mode(true)


const scrollerElem = ref(null)
const search = ref<SearchResult>(null)
const minSimilarityDist = computed(() => project.getTabManager().state.similarityDist ?? 80)
const state = reactive({
    sha1Scores: {}
})

const properties = computed(() => Object.keys(props.visibleProperties).map(k => project.data.properties[k]))

async function setSimilar() {
    if (!project.hasSimilaryFunction) return
    // if (modalMode.value != ImageModalMode.Similarity) return
    const res = await apiGetSimilarImages({ instanceIds: [props.image.id] })
    res.matches.sort((a, b) => b.score - a.score)
    search.value = res
    updateSimilarGroup()
}

function updateSimilarGroup() {
    if (!search.value) return

    var matches = search.value.matches.filter(i => i.score >= (minSimilarityDist.value / 100.0))

    const images = matches.map(m => project.data.images[m.id])
    state.sha1Scores = {}
    matches.forEach(m => state.sha1Scores[project.data.images[m.id].sha1] = m.score)

    similarGroup.group(images)

    if (scrollerElem.value) {
        scrollerElem.value.computeLines()
        scrollerElem.value.scrollTo('0')
    }

}

function setSimilarDist(value: number) {
    project.getTabManager().state.similarityDist = value
    similarGroup.clearSelection()
}

onMounted(setSimilar)
watch(() => props.image, setSimilar)
watch(minSimilarityDist, updateSimilarGroup)
watch(() => props.width, updateSimilarGroup)
</script>

<template>
    <div v-if="!project.hasSimilaryFunction" class="ps-2">No Similary Function found.</div>
    <template v-else>
        <div class="bg-white">
            <div class="d-flex mb-1">
                <SelectCircle v-if="similarGroup.hasResult()" :model-value="similarGroup.result.root.view.selected"
                    @update:model-value="v => similarGroup.toggleAll()" style="margin-top: -1px;" />
                <div style="margin-left: 6px;" class="me-3">Images Similaires</div>
                <wTT message="modals.image.similarity_filter_tooltip">
                    <RangeInput class="me-2" :min="0" :max="100" :model-value="minSimilarityDist"
                        @update:model-value="setSimilarDist" />
                </wTT>
                <div>min: {{ minSimilarityDist }}%</div>
                <div v-if="similarGroup.hasResult()" class="ms-2 text-secondary">({{
                    similarGroup.result.root.children.length }} images)</div>
            </div>


            <TreeScroller class="" :image-size="70" :height="props.height - 25" :width="props.width"
                :group-manager="similarGroup" :properties="properties" :hide-options="true" :hide-group="true"
                :sha1-scores="state.sha1Scores" ref="scrollerElem" />
        </div>
    </template>
</template>