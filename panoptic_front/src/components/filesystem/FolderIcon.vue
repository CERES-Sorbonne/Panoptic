<script setup lang="ts">
import { DirInfo } from '@/data/models';
import { computed } from 'vue';

const props = defineProps({
    dir: Object as () => DirInfo,
    selected: Boolean,
    isParent: Boolean,
    light: Boolean
})

const name = computed(() => props.dir.name)
const className = computed(() => {
    if(props.selected) return 'folder-name is-select'
    if(props.isParent) {
        if(props.light) return 'folder-name parent-select-light'
        else return 'folder-name parent-select'
    }
    return 'folder-name'
})

</script>

<template>
    <div :class="className" class="d-flex">
        <div v-if="props.dir.name == 'Home'" class="bi bi-house"></div>
        <div v-else-if="props.dir.name == 'Documents'" class="bi bi-file-earmark"></div>
        <div v-else-if="props.dir.name == 'Downloads'" class="bi bi-file-earmark-arrow-down"></div>
        <div v-else-if="props.dir.name == 'Desktop'" class="bi bi-display"></div>
        <div v-else-if="props.dir.name == 'Images' || props.dir.name == 'Pictures'" class="bi bi-image"></div>
        <div v-else class="bi bi-folder"></div>
        <div style="margin-left: 2px;">{{ props.dir.name }}</div>
        <div class="flex-grow-1"></div>
        <div v-if="dir.images" class="ms-2 end">{{ dir.images }}<i
                class="bi bi-images ms-1" /></div>
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
    color: white;
}


.is-select {
    background-color: rgb(3, 100, 225);
    color: white;
}

.parent-select {
    background-color: rgb(201, 202, 203);
    color: black;
}

.parent-select-light {
    background-color: rgb(221, 222, 223);
    color: black;
}
</style>