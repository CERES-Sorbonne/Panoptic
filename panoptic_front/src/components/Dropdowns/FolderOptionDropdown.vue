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
        <template #button><i class="bi bi-three-dots base-hover"></i></template>
        <template #popup="{ hide }">
            <div class="text-nowrap">
                <div class="p-2 bb" @click="reImport(); hide();"><i class="bi bi-arrow-clockwise me-1"></i>Re import</div>
                <div class="custom-hr"></div>
                <div class="bb p-2" @click="deleteFolder(); hide();"><i class="bi bi-trash me-1"></i>{{ $t('main.nav.folders.del') }}</div>
            </div>
        </template>
    </Dropdown>
</template>