<script setup lang="ts">
import { GroupManager } from '@/core/GroupManager';
import { Image } from '@/data/models';
import { computed, onMounted, reactive, ref, watch } from 'vue';
import wTT from '@/components/tooltips/withToolTip.vue'
import TreeScroller from '@/components/scrollers/tree/TreeScroller.vue';
import RangeInput from '@/components/inputs/RangeInput.vue';
import SelectCircle from '@/components/inputs/SelectCircle.vue';
import { getSimilarImages } from '@/utils/utils';
import { useProjectStore } from '@/data/projectStore';
const project = useProjectStore()

const props = defineProps<{
    image: Image
    width: number
    height: number
    similarGroup?: GroupManager
    visibleProperties: {[id: number]: boolean}
}>()
const similarGroup = props.similarGroup ?? new GroupManager()
similarGroup.setSha1Mode(true)


const scrollerElem = ref(null)
const similarImages = ref([])
const minSimilarityDist = ref(80)
const state = reactive({
    sha1Scores: {}
})

const properties = computed(() => Object.keys(props.visibleProperties).map(k => project.data.properties[k]))

async function setSimilar() {
    // if (modalMode.value != ImageModalMode.Similarity) return

    const res = await getSimilarImages({instanceIds: [props.image.id]})
    similarImages.value = res
    updateSimilarGroup()
}

function updateSimilarGroup() {
    var filteredSha1s = similarImages.value.filter(i => i.dist >= (minSimilarityDist.value / 100.0))

    const images: Image[] = []
    state.sha1Scores = {}
    filteredSha1s.forEach(r => images.push(...project.data.sha1Index[r.sha1]))
    filteredSha1s.forEach(r => state.sha1Scores[r.sha1] = r.dist)

    similarGroup.group(images)

    if (scrollerElem.value) {
        scrollerElem.value.computeLines()
        scrollerElem.value.scrollTo('0')
    }

}

onMounted(setSimilar)
watch(() => props.image, setSimilar)
watch(minSimilarityDist, updateSimilarGroup)
watch(() => props.width, updateSimilarGroup)
</script>

<template>
    <div class="bg-white">
        <div class="d-flex mb-1">
        <SelectCircle v-if="similarGroup.hasResult()" :model-value="similarGroup.result.root.view.selected"
            @update:model-value="v => similarGroup.toggleAll()" style="margin-top: -1px;"/>
        <div style="margin-left: 6px;" class="me-3">Images Similaires</div>
        <wTT message="modals.image.similarity_filter_tooltip">
            <RangeInput class="me-2" :min="0" :max="100" v-model="minSimilarityDist"
                @update:model-value="similarGroup.clearSelection()" />
        </wTT>
        <div>min: {{ minSimilarityDist }}%</div>
        <div v-if="similarGroup.hasResult()" class="ms-2 text-secondary">({{
            similarGroup.result.root.children.length }} images)</div>
    </div>


    <TreeScroller class="" :image-size="70" :height="props.height-25" :width="props.width" :group-manager="similarGroup"
        :properties="properties" :hide-options="true" :hide-group="true" :sha1-scores="state.sha1Scores" ref="scrollerElem" />
    </div>

</template>