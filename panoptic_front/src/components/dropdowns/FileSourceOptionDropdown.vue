<script setup lang="ts">
import { ref } from 'vue';
import { FileSource } from '@/data/models';
import Dropdown from './Dropdown.vue';
import { i18n } from '@/main';
import { useDataStore } from '@/data/dataStore';

const data = useDataStore()

const props = defineProps<{
    source: FileSource
}>()

const testStatus = ref<'idle' | 'checking' | 'connected' | 'error'>('idle')

const testLabel: Record<typeof testStatus.value, string> = {
    idle: 'Test connection',
    checking: 'Testing…',
    connected: 'Connected',
    error: 'Connection failed',
}

function testConnection() {
    testStatus.value = 'checking'
    // TODO: replace with a real API call once the backend exposes a connection-test endpoint
    setTimeout(() => {
        testStatus.value = 'connected'
    }, 800)
}

function formatSyncDate(iso: string) {
    return new Date(iso).toLocaleString()
}

function resyncFileSource(hide: () => void) {
    data.resyncFileSource(props.source.id)
    hide()
}

function deleteFileSource(hide: () => void) {
    const ok = confirm(i18n.global.t("main.nav.fileSources.del_alert"))
    if (ok) {
        data.deleteFileSource(props.source.id)
    }
    hide()
}
</script>

<template>
    <Dropdown :teleport="true">
        <template #button><i class="bi bi-three-dots-vertical base-hover"></i></template>
        <template #popup="{ hide }">
            <div class="project-menu">
                <template v-if="source.dtype === 'iiif'">
                    <div class="url-row" :title="source.rootUrl ?? ''">{{ source.rootUrl }}</div>
                    <div class="menu-item" @click="testConnection()">
                        <i class="bi bi-plug"></i>
                        <span>{{ testLabel[testStatus] }}</span>
                    </div>
                </template>
                <div class="sync-row" v-if="source.syncStatus">
                    <div>{{ $t('main.nav.fileSources.sync.counts', {
                        folders: source.syncStatus.folderCount, files: source.syncStatus.fileCount
                    }) }}</div>
                    <div>{{ $t('main.nav.fileSources.sync.lastSynced', {
                        date: formatSyncDate(source.syncStatus.lastSyncedAt)
                    }) }}</div>
                </div>
                <div class="sync-row" v-else>{{ $t('main.nav.fileSources.sync.neverSynced') }}</div>
                <div class="menu-item" @click="resyncFileSource(hide)">
                    <i class="bi bi-arrow-clockwise"></i>
                    <span>{{ $t('main.nav.fileSources.sync.resync') }}</span>
                </div>
                <div class="menu-item" @click="deleteFileSource(hide)">
                    <i class="bi bi-trash"></i>
                    <span>{{ $t('main.nav.fileSources.del') }}</span>
                </div>
            </div>
        </template>
    </Dropdown>
</template>

<style scoped>
.project-menu {
    padding: 3px;
}

.url-row {
    padding: 4px 10px 4px 8px;
    color: var(--text-secondary);
    font-size: var(--font-size-sm);
    max-width: 280px;
    overflow-wrap: break-word;
}

.sync-row {
    padding: 4px 10px 4px 8px;
    color: var(--text-secondary);
    font-size: var(--font-size-sm);
}

.menu-item {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 4px 10px 4px 8px;
    border-radius: var(--radius-sm);
    cursor: pointer;
    white-space: nowrap;
    color: var(--text-secondary);
    font-size: var(--font-size-sm);
    border: none;
    background: none;
    width: 100%;
    justify-content: flex-start;
}

.menu-item:hover {
    background-color: var(--hover-bg);
    color: var(--text-primary);
}
</style>
