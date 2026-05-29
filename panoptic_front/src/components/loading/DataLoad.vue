<script setup lang="ts">
import { computed } from 'vue'
import { useColumnStore } from '@/data/columnStore'
import { useDataStore } from '@/data/dataStore'
import LoadWheel from './LoadWheel.vue'
import Percentage from './Percentage.vue'

const colStore = useColumnStore()
const data     = useDataStore()

const loadingColumns = computed(() =>
    Object.entries(colStore.fullColumnStatus)
        .filter(([, status]) => status === 'loading')
        .map(([idStr]) => {
            const id = Number(idStr)
            return { id, name: data.properties[id]?.name ?? `#${id}` }
        })
)
const showPanel = computed(() => !data.isLoaded || loadingColumns.value.length > 0)

const state = computed(() => data.loadState)
const pct = computed(() => {
    if (!state.value || !state.value.maxInstance) return 0
    return Math.round(state.value.counterInstance / state.value.maxInstance * 100)
})
</script>

<template>
    <div v-if="showPanel" class="center">
        <div class="text-start" style="display: inline-block; min-width: 220px;">

            <!-- Init phase: main stream in progress -->
            <template v-if="!data.isLoaded">
                <div class="d-flex align-items-center text-secondary row-gap mb-1">
                    <div class="label">Folders</div>
                    <LoadWheel class="me-2" :loading="!data.folderRoots.length" />
                    <i v-if="data.folderRoots.length" class="bi bi-check text-success" />
                </div>
                <div class="d-flex align-items-center text-secondary row-gap mb-1">
                    <div class="label">Properties</div>
                    <LoadWheel class="me-2" :loading="!state?.finishedProperty" />
                    <i v-if="state?.finishedProperty" class="bi bi-check text-success" />
                </div>
                <div class="d-flex align-items-center text-secondary row-gap mb-1">
                    <div class="label">Tags</div>
                    <LoadWheel class="me-2" :loading="!state?.finishedTags" />
                    <i v-if="state?.finishedTags" class="bi bi-check text-success" />
                </div>
                <div class="d-flex align-items-center text-secondary row-gap">
                    <div class="label">Instances</div>
                    <LoadWheel class="me-2" :loading="!state?.finishedInstance" />
                    <i v-if="state?.finishedInstance" class="bi bi-check text-success" />
                    <Percentage :current="pct" :max="100" :force="!!state?.finishedInstance" />
                    <span v-if="colStore.instanceCount > 0" class="ms-1" style="font-size:12px;">{{ colStore.instanceCount.toLocaleString() }}</span>
                </div>
            </template>

            <!-- Column fetch phase: on-demand column loads -->
            <template v-if="loadingColumns.length">
                <div class="section-title text-secondary mt-2 mb-1">Columns</div>
                <div
                    v-for="col in loadingColumns"
                    :key="col.id"
                    class="d-flex align-items-center text-secondary row-gap"
                >
                    <div class="label">{{ col.name }}</div>
                    <LoadWheel :loading="true" />
                </div>
            </template>

        </div>
    </div>
</template>

<style scoped>
.center {
    display: flex;
    justify-content: center;
    align-items: center;
}

.label {
    width: 120px;
    font-size: 14px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.row-gap {
    gap: 4px;
}

.section-title {
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    opacity: 0.6;
}
</style>
