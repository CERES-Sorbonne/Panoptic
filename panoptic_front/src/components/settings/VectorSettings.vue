<script setup lang="ts">
import { useDataStore } from '@/data/dataStore';
import SectionDivider from '../utils/SectionDivider.vue';
import ActionButton from '../actions/ActionButton.vue';
import ActionSelect from '../actions/ActionSelect.vue';
import ActionSelectFlat from '../actions/ActionSelectFlat.vue';
import { ref } from 'vue';

const data = useDataStore()

const create = ref(false)
const compute = ref(false)

async function deleteType(id: number) {
    await data.deleteVectorType(id)
}

</script>

<template>
    <div class="main">

        <SectionDivider>
            Registered Vector Types
        </SectionDivider>

        <table class="mb-3">
            <thead>
                <tr>
                    <th></th>
                    <th>ID</th>
                    <th>Source</th>
                    <th>Params</th>
                </tr>
            </thead>
            <tbody>
                <tr v-for="vecType in data.vectorTypes" :key="vecType.id">
                    <td><i class="bb bi bi-x" @click="deleteType(vecType.id)"/></td>
                    <td>{{ vecType.id }}</td>
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
        <div v-if="!create">
            <span class="bb" @click="create = true">Create New Type <i class="bi bi-plus" /></span>
        </div>
        <SectionDivider v-if="create"><span style="margin-left: 3px;">Create New Type</span></SectionDivider>
        <div v-if="create">
            <ActionSelectFlat :action="'vector_type'" :size="15" @cancel="create = false" @added="data.updateVectorTypes()" />
        </div>
         <div v-if="!compute">
            <span class="bb" @click="compute = true">Compute Vectors <i class="bi bi-plus" /></span>
        </div>
        <SectionDivider v-if="compute"><span style="margin-left: 3px;">Compute Vectors</span></SectionDivider>
        <div v-if="compute">
            <ActionSelectFlat :action="'vector'" :size="15" @cancel="compute = false"/>
        </div>
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