<script setup lang="ts">
import { DirInfo } from '@/data/models';
import { directiveHooks } from '@vueuse/core';
import { computed } from 'vue';

const props = defineProps({
    dir: Object as () => DirInfo,
    selectedPath: String,
    baseRoot: String
})

const name = computed(() => props.dir.name)
const isSelected = computed(() => props.selectedPath.startsWith(props.dir.path) && props.dir.path.length >= props.baseRoot.length)

</script>

<template>
    <div class="folder-name" :class="(isSelected ? 'selected' : '')">
        <span v-if="props.dir.name == 'Home'" class="bi bi-house"></span>
        <span v-else-if="props.dir.name == 'Documents'" class="bi bi-file-earmark"></span>
        <span v-else-if="props.dir.name == 'Downloads'" class="bi bi-file-earmark-arrow-down"></span>
        <span v-else-if="props.dir.name == 'Desktop'" class="bi bi-display"></span>
        <span v-else-if="props.dir.name == 'Images' || props.dir.name == 'Pictures'" class="bi bi-image"></span>
        <span v-else class="bi bi-folder"></span>
        {{ props.dir.name }}
        <span v-if="dir.images" class="float-end ms-2"><span class="text-secondary">{{ dir.images }}</span><i
                class="bi bi-images ms-1" /></span>
    </div>
</template>

<style scoped>
.folder-name {
    padding: 3px 5px;
    cursor: pointer;
    border-radius: 5px;
    text-wrap: nowrap !important;
    white-space: nowrap !important;
}

.folder-name:hover {
    background-color: rgb(3, 100, 225);
}


.selected {
    background-color: rgb(201, 202, 203);
}
</style>