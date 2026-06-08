<script setup lang="ts">
import { Folder } from '@/data/models';
import Dropdown from './Dropdown.vue';
import { i18n } from '@/main';
import { useDataStore } from '@/data/dataStore';

const data = useDataStore()

const props = defineProps<{
    folder: Folder
}>()

function reImport() {
    data.reImportFolder(props.folder.id)
}

function deleteFolder() {
    const ok = confirm(i18n.global.t("main.nav.folders.del_alert"))
    if(ok) {
        data.deleteFolder(props.folder.id)
    }
}

</script>

<template>
    <Dropdown :teleport="true">
        <template #button><i class="bi bi-three-dots-vertical base-hover"></i></template>
        <template #popup="{ hide }">
            <div class="project-menu">
                <div class="menu-item" @click="reImport(); hide()">
                    <i class="bi bi-arrow-clockwise"></i>
                    <span>Re import</span>
                </div>
                <div class="menu-item" @click="deleteFolder(); hide()">
                    <i class="bi bi-trash"></i>
                    <span>{{ $t('main.nav.folders.del') }}</span>
                </div>
            </div>
        </template>
    </Dropdown>
</template>

<style scoped>
.project-menu {
    padding: 3px;
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
