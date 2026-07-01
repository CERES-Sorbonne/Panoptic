<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { DbCommitInfo } from '@/data/models'
import { apiGetCommits, apiSetCommitActive, apiCompact } from '@/data/apiProjectRoutes'
import SectionDivider from '../utils/SectionDivider.vue'

const commits = ref<DbCommitInfo[]>([])
const loading = ref(false)
const confirmCompactId = ref<number | null>(null)
const busy = ref(false)

async function refresh() {
    loading.value = true
    try {
        commits.value = await apiGetCommits()
    } finally {
        loading.value = false
    }
}

async function toggle(commit: DbCommitInfo) {
    if (busy.value) return
    busy.value = true
    try {
        await apiSetCommitActive(commit.id, !commit.active)
        // The grid refreshes itself via the db_update socket delta; refresh our own list.
        await refresh()
    } finally {
        busy.value = false
    }
}

function askCompact(commit: DbCommitInfo) {
    confirmCompactId.value = commit.id
}

function cancelCompact() {
    confirmCompactId.value = null
}

async function doCompact(commit: DbCommitInfo) {
    if (busy.value) return
    busy.value = true
    try {
        await apiCompact(commit.id)
        confirmCompactId.value = null
        await refresh()
    } finally {
        busy.value = false
    }
}

function formatWhen(ts: string) {
    const d = new Date(ts)
    return d.toLocaleString()
}

onMounted(refresh)
defineExpose({ refresh })
</script>

<template>
    <div class="h-100 w-100 overflow-auto p-3">
        <SectionDivider :text="$t('modals.settings.dataPage.title')" />
        <div class="text-secondary mb-2" style="font-size: 13px;">
            {{ $t('modals.settings.dataPage.info') }}
        </div>

        <div v-if="loading" class="text-secondary">…</div>
        <div v-else-if="!commits.length" class="text-secondary">
            {{ $t('modals.settings.dataPage.empty') }}
        </div>

        <table v-else class="table-sm w-100" style="border-collapse: collapse;">
            <thead>
                <tr class="text-secondary" style="border-bottom: 1px solid var(--border-color); font-size: 12px;">
                    <th class="p-1 text-center">{{ $t('modals.settings.dataPage.enabled') }}</th>
                    <th class="p-1 text-start">#</th>
                    <th class="p-1 text-start">{{ $t('modals.settings.dataPage.when') }}</th>
                    <th class="p-1 text-start">{{ $t('modals.settings.dataPage.author') }}</th>
                    <th class="p-1 text-start">{{ $t('modals.settings.dataPage.source') }}</th>
                    <th class="p-1 text-end"></th>
                </tr>
            </thead>
            <tbody>
                <tr v-for="commit in commits" :key="commit.id"
                    :class="{ 'text-secondary': !commit.active }"
                    style="border-bottom: 1px solid var(--border-color);">
                    <td class="p-1 text-center">
                        <div class="form-check form-switch d-inline-block m-0">
                            <input class="form-check-input" type="checkbox" role="switch"
                                :checked="!!commit.active" :disabled="busy" @change="toggle(commit)" />
                        </div>
                    </td>
                    <td class="p-1" :style="commit.active ? '' : 'text-decoration: line-through;'">{{ commit.id }}</td>
                    <td class="p-1">{{ formatWhen(commit.timestamp) }}</td>
                    <td class="p-1">{{ commit.author || commit.source }}</td>
                    <td class="p-1"><span class="badge bg-light text-secondary">{{ commit.source }}</span></td>
                    <td class="p-1 text-end">
                        <template v-if="confirmCompactId === commit.id">
                            <span class="text-danger me-2" style="font-size: 12px;">
                                {{ $t('modals.settings.dataPage.compactConfirm') }}
                            </span>
                            <span class="bb text-danger me-2" @click="doCompact(commit)">
                                {{ $t('modals.settings.dataPage.confirm') }}
                            </span>
                            <span class="bb text-secondary" @click="cancelCompact">
                                {{ $t('modals.settings.dataPage.cancel') }}
                            </span>
                        </template>
                        <span v-else class="bb text-secondary" @click="askCompact(commit)">
                            <i class="bi bi-archive me-1" />{{ $t('modals.settings.dataPage.compact') }}
                        </span>
                    </td>
                </tr>
            </tbody>
        </table>
    </div>
</template>

<style scoped>
.bb {
    cursor: pointer;
    font-size: 13px;
}
.bb:hover {
    text-decoration: underline;
}
th, td {
    white-space: nowrap;
}
</style>
