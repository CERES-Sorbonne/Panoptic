<script setup lang="ts">
import { useMediaStore } from '@/data/stores/mediaStore';
import SectionDivider from '../utils/SectionDivider.vue';
import ActionButton from '../actions/ActionButton.vue';
import ActionSelect from '../actions/ActionSelect.vue';
import ActionSelectFlat from '../actions/ActionSelectFlat.vue';
import { computed, onMounted, ref } from 'vue';
import { VectorType } from '@/data/models';
import { useActionStore } from '@/data/stores/actionStore';
import ComputeVectorButton from './ComputeVectorButton.vue';

const media = useMediaStore()
const actions = useActionStore()

const create = ref(false)
const compute = ref(false)
async function deleteType(id: number) {
    await media.deleteVectorType(id)
}

// Width of each number, in characters: enough for the total, so the counts keep their
// place while they update.
const numberWidth = computed(() => String(media.vectorStats.sha1Count).length + 'ch')

// Share of the project's images with a vector of this type
function coveragePercent(vecType: VectorType) {
    const total = media.vectorStats.sha1Count
    return total > 0 ? Math.round(100 * media.vectorCount(vecType.id) / total) : 0
}

async function computeVectors(vecType: VectorType) {
    await actions.callComputeVector(vecType)
}

onMounted(() => media.updateVectorStats())


</script>

<template>
    <div class="main">
        <SectionDivider>
            {{$t('modals.settings.registeredVectorTypes')}}
        </SectionDivider>
        <table class="mb-3">
            <thead>
                <tr>
                    <th></th>
                    <th>{{$t('modals.settings.id')}}</th>
                    <th>{{$t('modals.settings.computed')}}</th>
                    <th>{{$t('modals.settings.source')}}</th>
                    <th>{{$t('modals.settings.params')}}</th>
                </tr>
            </thead>
            <tbody>
                <tr v-for="vecType in media.vectorTypes" :key="vecType.id">
                    <td><i class="bb bi bi-x" @click="deleteType(vecType.id)" /></td>
                    <td>{{ vecType.id }}</td>
                    <td>
                        <div class="d-flex align-items-center">
                            <span class="counts">
                                <span class="count" :style="{ width: numberWidth }">{{ media.vectorCount(vecType.id) }}</span>
                                /
                                <span class="count" :style="{ width: numberWidth }">{{ media.vectorStats.sha1Count }}</span>
                            </span>
                            <div class="count-action ms-2">
                                <div v-if="media.vectorTask(vecType.id)" class="task-track">
                                    <div class="task-fill" :style="{ width: coveragePercent(vecType) + '%' }" />
                                </div>
                                <ComputeVectorButton v-else-if="media.vectorCount(vecType.id) != media.vectorStats.sha1Count" :vector-type="vecType" />
                            </div>
                        </div>
                    </td>
                    <td>{{ vecType.source }}</td>
                    <td>
                        <div class="d-flex">
                            <div v-for="(value, key) in vecType.params" :key="key" class="me-2">
                                <span class="text-secondary">{{ key }}</span>: <span class="">{{ value }}</span>
                            </div>
                        </div>
                    </td>
                </tr>
            </tbody>
        </table>
        <div v-if="!create && actions.hasVectorFunction">
            <span class="bb" @click="create = true">{{$t('modals.settings.createNewVectorType')}} <i class="bi bi-plus" /></span>
        </div>
        <SectionDivider v-if="create"><span style="margin-left: 3px;">{{$t('modals.settings.createNewVectorType')}}</span></SectionDivider>
        <div v-if="create">
            <ActionSelectFlat :action="'vector_type'" :size="15" @cancel="create = false"
                @added="media.updateVectorTypes()" />
        </div>
        <!-- <div v-if="!compute">
            <span class="bb" @click="compute = true">Compute Vectors <i class="bi bi-plus" /></span>
        </div> -->
        <!-- <SectionDivider v-if="compute"><span style="margin-left: 3px;">Compute Vectors</span></SectionDivider>
        <div v-if="compute">
            <ActionSelectFlat :action="'vector'" :size="15" @cancel="compute = false" />
        </div> -->
    </div>
</template>

<style scoped>
.main {
    padding: 5px;
}

.counts {
    font-family: monospace;
    white-space: nowrap;
}

.count {
    display: inline-block;
    text-align: right;
}

/* Minimum width so the column keeps its size between the button and the bar.
   It still grows when the translated button label is longer. */
.count-action {
    min-width: 80px;
    display: flex;
    align-items: center;
    white-space: nowrap;
}

.task-track {
    position: relative;
    width: 80px;
    height: 5px;
    background: #e9ecef;
    border-radius: 3px;
    overflow: hidden;
}

.task-fill {
    height: 100%;
    background: #4dabf7;
    transition: width 0.2s linear;
}

table {
    border-collapse: separate;
    border-spacing: 16px 0;
    /* Horizontal: 16px, Vertical: 0px */
}
</style>