<script setup lang="ts">
import { ProjectVectorDescription } from '@/data/models';
import { useProjectStore } from '@/data/projectStore';
import {  ref, onMounted, watch, computed } from 'vue';
const project = useProjectStore()

const localVectors = ref<ProjectVectorDescription>(null)

const changed = computed(() => {
    if(!localVectors.value) return false
    // if(!project.data.vectors.defaultVectors && localVectors.value.defaultVectors) return true

    const local = JSON.stringify(localVectors.value.defaultVectors)
    const db = JSON.stringify(project.data.vectors.defaultVectors)
    return local != db
})

function load() {
    localVectors.value = JSON.parse(JSON.stringify(project.data.vectors))
}

function apply() {
    project.setDefaultVectors(localVectors.value.defaultVectors)
}

onMounted(load)
watch(project.data.plugins, load)

</script>

<template>
    <div class="main">
        <h4 class="text-center">Vectors</h4>
        <div v-if="localVectors" class="d-flex p-2">
            <div class="me-2">Default Vectors</div>
            <select v-model="localVectors.defaultVectors">
                <option v-for="v in localVectors.vectors" :value="v">{{ v.source }}.{{ v.type }} ({{ v.count }})</option>
            </select>
        </div>
        <div v-if="changed" class="d-flex changed">
            <div class="flex-grow-1"></div>
            <div class="base-btn me-3" @click="load">Reset</div>
            <div class="base-btn" @click="apply">Update</div>
        </div>
    </div>
</template>

<style scoped>
.main {
    border: 1px solid var(--border-color);
    border-radius: 3px;
    /* padding: 5px; */
}

.changed {
    /* border-top: 1px solid var(--border-color); */
    padding: 5px;
}
</style>