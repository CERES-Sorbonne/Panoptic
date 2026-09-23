<script setup lang="ts">
import { Folder } from '@/data/models';
import Dropdown from './Dropdown.vue';
import { i18n } from '@/locales/i18n';
import { useDataStore } from '@/data/stores/dataStore';

const data = useDataStore()

const props = defineProps<{
    folder: Folder
}>()
const emit = defineEmits(['show', 'hide'])

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
    <Dropdown :teleport="true" @show="emit('show')" @hide="emit('hide')">
        <template #button><span class="folder-act"><i class="bi bi-three-dots"></i></span></template>
        <template #popup="{ hide }">
            <div class="project-menu">
                <div class="menu-item" @click="reImport(); hide()">
                    <i class="bi bi-arrow-clockwise"></i>
                    <span>{{ $t('main.nav.folders.reimport') }}</span>
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
/* Same look as the property row action buttons (PropertyOptions .prop-act) */
.folder-act {
    width: 18px;
    height: 18px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: var(--radius-sm);
    font-size: 12px;
    color: var(--text-tertiary);
    cursor: pointer;
}

.folder-act:hover {
    background-color: var(--hover-bg);
    color: var(--text-primary);
}

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
