<script setup lang="ts">
import { computed } from 'vue'
import { useColumnStore } from '@/data/dataStore2'
import { useDataStore } from '@/data/dataStore'
import LoadWheel from './LoadWheel.vue'
import Percentage from './Percentage.vue'

const colStore = useColumnStore()
const data     = useDataStore()

const foldersReady = computed(() => data.folderRoots.length > 0)

const loadingColumns = computed(() =>
    Object.entries(colStore.fullColumnStatus)
        .filter(([, status]) => status === 'loading')
        .map(([idStr]) => {
            const id = Number(idStr)
            return { id, name: data.properties[id]?.name ?? `#${id}` }
        })
)
const showPanel = computed(() => !colStore.isReady || loadingColumns.value.length > 0)
</script>

<template>
    <div v-if="showPanel" class="center">
        <div class="text-start" style="display: inline-block; min-width: 220px;">

            <!-- Init phase: slim stream in progress -->
            <template v-if="!colStore.isReady">
                <div class="d-flex align-items-center text-secondary row-gap mb-1">
                    <div class="label">Folders</div>
                    <LoadWheel class="me-2" :loading="!foldersReady" />
                    <i v-if="foldersReady" class="bi bi-check text-success" />
                </div>
                <div class="d-flex align-items-center text-secondary row-gap mb-1">
                    <div class="label">Properties</div>
                    <LoadWheel class="me-2" :loading="!colStore.propertiesReady" />
                    <i v-if="colStore.propertiesReady" class="bi bi-check text-success" />
                </div>
                <div class="d-flex align-items-center text-secondary row-gap mb-1">
                    <div class="label">Tags</div>
                    <LoadWheel class="me-2" :loading="!colStore.tagsReady" />
                    <i v-if="colStore.tagsReady" class="bi bi-check text-success" />
                </div>
                <div class="d-flex align-items-center text-secondary row-gap">
                    <div class="label">Instances</div>
                    <LoadWheel class="me-2" :loading="!colStore.isReady" />
                    <i v-if="colStore.isReady" class="bi bi-check text-success" />
                    <Percentage
                        :current="colStore.initProgress.current"
                        :max="colStore.initProgress.total"
                        :force="colStore.isReady"
                    />
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
