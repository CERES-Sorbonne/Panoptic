<script setup lang="ts">
import { Folder } from '@/data/models';
import Dropdown from './Dropdown.vue';
import { useProjectStore } from '@/data/projectStore';

const project = useProjectStore()

const props = defineProps<{
    folder: Folder
}>()

function reImport() {
    project.reImportFolder(props.folder.id)
}

</script>

<template>
    <Dropdown :teleport="true">
        <template #button><i class="bi bi-three-dots base-hover"></i></template>
        <template #popup="{hide}">
            <div class="p-2">
                <div class="base-hover p-1" @click="reImport(); hide();"><i class="bi bi-arrow-clockwise"></i> Re import</div>
            </div>
        </template>
    </Dropdown>
</template>