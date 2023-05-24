<script setup lang="ts">
import { Folder } from '@/data/models';
import {globalStore} from '@/data/store'
import { computed } from 'vue';

const props = defineProps({
    folders: Array<Folder>,
    root: {type: Boolean, default: true}
})

function toggleFolder(folderId: number) {
    let folder = globalStore.folders[folderId]
    if(folder.show) {
        folder.show = false
    }
    else {
        folder.show = true
    }
}

function toggleFolderSelect(folderId: number) {
    let folder = globalStore.folders[folderId]
    if(folder.selected) {
        folder.selected = false
    }
    else {
        folder.selected = true
    }
}

function folderClass(folder: Folder) {
    let classes = []
    if(folder.selected) classes.push('selected')

    return classes.join(' ')
}

</script>

<template>
    <ul :class="props.root ? 'tree' : ''" :style="props.root ? 'padding-left:0px;' : ''">
        <li v-for="folder in folders" :style="props.root ? 'padding-left:0px;' : ''">
            <summary :class="folderClass(folder)" @click="toggleFolderSelect(folder.id)">{{ folder.name }}</summary>
            <i v-if="folder.children && folder.children.length > 0" @click="toggleFolder(folder.id)" :class="'bi bi-chevron-' + (folder.show ? 'down' : 'right') + ' ms-2 btn-icon'" style="font-size: 9px;"></i>
            <template v-if="folder.children && folder.children.length > 0 && folder.show">
                <FolderList :folders="folder.children" :root="false"/>
            </template>
        </li>
    </ul>
</template>

<style scoped>

.selected {
    border: 1px solid blue;
    padding: 2px 4px !important;
    
}

.tree {
    text-align: start;
    --spacing: 1.3rem;
    --radius: 30px;
    margin-bottom: 0;
}

.tree li {
    display: block;
    position: relative;
    margin-left: 0;
    padding-left: calc(2 * var(--spacing) - var(--radius) - 0px);
}

.tree ul {
    margin-left: calc(var(--radius) - var(--spacing));
    /* margin-left: 0; */
    padding-left: 0;
    margin-bottom: 0;
}

.tree ul li {
    border-left: 1px solid rgb(195, 207, 217);
}

.tree ul li:last-child {
    border-color: transparent;
}

.tree ul li::before {
    content: '';
    display: block;
    position: absolute;
    top: calc(var(--spacing) / -2);
    left: -1px;
    width: calc(var(--spacing) + 1px);
    height: calc(var(--spacing) + 3px);
    border: solid rgb(195, 207, 217);
    border-width: 0 0 1px 1px;
}

.tree summary {
    text-align: center;
    display: inline-block;
    position: relative;
    cursor: pointer;
    z-index: 10 !important;
    background-color: rgb(195, 207, 217);
    margin: 3px 0px 0px 0px;
    border-radius: 2px;
    padding: 3px 5px;
    /* min-width: 30px; */
    font-size: 10px;
    width: auto;
}

.tree summary::marker,
.tree summary::-webkit-details-marker {
    display: none;
}

.tree summary:focus {
    outline: none;
}

.tree summary:focus-visible {
    outline: 1px dotted #000;
}
</style>