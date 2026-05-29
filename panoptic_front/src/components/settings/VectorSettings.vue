<script setup lang="ts">
import { useMediaStore } from '@/data/mediaStore';
import SectionDivider from '../utils/SectionDivider.vue';
import ActionButton from '../actions/ActionButton.vue';
import ActionSelect from '../actions/ActionSelect.vue';
import ActionSelectFlat from '../actions/ActionSelectFlat.vue';
import { computed, onMounted, ref } from 'vue';
import { VectorType } from '@/data/models';
import { useActionStore } from '@/data/actionStore';
import ComputeVectorButton from './ComputeVectorButton.vue';

const media = useMediaStore()
const actions = useActionStore()

const create = ref(false)
const compute = ref(false)
async function deleteType(id: number) {
    await media.deleteVectorType(id)
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
                        <div>
                            <ComputeVectorButton v-if="media.vectorStats.count[vecType.id] != media.vectorStats.sha1Count" :vector-type="vecType" class="me-2" />
                            <span v-if="media.vectorStats.count[vecType.id] != undefined">{{ media.vectorStats.count[vecType.id] }} / {{ media.vectorStats.sha1Count }}</span>
                            <span v-else>0 / {{ media.vectorStats.sha1Count }}</span>
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

table {
    border-collapse: separate;
    border-spacing: 16px 0;
    /* Horizontal: 16px, Vertical: 0px */
}
</style>