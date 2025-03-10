<script setup lang="ts">
import { FilterManager } from '@/core/FilterManager';
import { Folder } from '@/data/models';
import { getFolderChildren, getFolderAndParents } from '@/utils/utils';
import { computed, ref } from 'vue';
import FolderOptionDropdown from '../dropdowns/FolderOptionDropdown.vue';
import { useDataStore } from '@/data/dataStore';

const data = useDataStore()
const props = defineProps({
    folders: Array<Folder>,
    visibleFolders: Object as () => { [folderId: number]: boolean },
    filterManager: FilterManager,
    root: { type: Boolean, default: true }
})

const hoverId = ref(null)

const isSelected = computed(() => {
    let res = {} as any
    const folderSet = new Set(props.filterManager.state.folders)
    props.folders.map(f => f.id).forEach(id => {
        if (folderSet.has(id)) {
            res[id] = true
        }
    })
    return res
})

const isVisible = computed(() => {
    let res = {} as any
    props.folders.map(f => f.id).forEach(id => {
        if (props.visibleFolders[id]) {
            res[id] = true
        }
    })
    return res
})

const folderClass = computed(() => {
    let res = {} as any
    props.folders.forEach(f => {
        let classes = []
        if (isSelected.value[f.id]) classes.push('selected')

        res[f.id] = classes.join(' ')
    })

    return res
})

function toggleFolderVisible(folderId: number) {
    let visible = props.visibleFolders
    if (visible[folderId]) {
        delete visible[folderId]
    }
    else {
        visible[folderId] = true
    }
}

function toggleFolderSelect(folderId: number) {
    let selected = new Set(props.filterManager.state.folders)
    const isSelected = selected.has(folderId)
    const isParentSelected = data.folders[folderId].parent != undefined && selected.has(data.folders[folderId].parent)
    if (isSelected && !isParentSelected) {
        selected.delete(folderId)
        getFolderChildren(folderId).forEach(c => selected.delete(c.id))
    }
    else {
        unselectParent(folderId, selected)
        selected.add(folderId)
        getFolderChildren(folderId).forEach(c => selected.add(c.id))
        getFolderAndParents(data.folders[folderId]).forEach(c => selected.delete(c.id))
    }

    props.filterManager.setFolders(Array.from(selected))

    props.filterManager.update(true)
}

function unselectParent(folderId: number, selected: Set<number>) {
    const parents = getFolderAndParents(data.folders[folderId])
    let highestParent = undefined
    for (let p of parents) {
        if (selected.has(p.id)) {
            highestParent = p
        } else {
            break
        }
    }
    if (highestParent != undefined) {
        getFolderChildren(highestParent.id).forEach(c => selected.delete(c.id))
    }
}

</script>

<template>
    <ul :class="props.root ? 'tree' : ''" :style="props.root ? 'padding-left:0px;' : ''">
        <li v-for="folder in folders" :style="props.root ? 'padding-left:0px;' : ''" class="no-break">
            <div style="display: inline;" @mouseenter="hoverId = folder.id" @mouseleave="hoverId = null">
                <summary :class="folderClass[folder.id]" @click="toggleFolderSelect(folder.id)">
                    <span :class="hoverId === folder.id ? 'visible-option' : 'invisible-option'" @click.stop="">
                        <FolderOptionDropdown :folder="folder"/>
                    </span>
                    {{ folder.name }}
                    <span class="text-secondary">{{ data.folders[folder.id].count }}</span>
                </summary>
            </div>
            <i v-if="folder.children && folder.children.length > 0" @click="toggleFolderVisible(folder.id)"
                :class="'bi bi-chevron-' + (isVisible[folder.id] ? 'down' : 'right') + ' ms-2 btn-icon'"
                style="font-size: 9px;"></i>
            <template v-if="folder.children && folder.children.length > 0 && isVisible[folder.id]">
                <FolderList2 :folders="folder.children" :root="false" :visible-folders="props.visibleFolders"
                    :filter-manager="props.filterManager" />
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

.no-break {
    word-wrap: none;
    word-break: none;
    white-space: nowrap;
}

.visible-option {
    /* padding-left: 3px; */
    /* position: relative;
    top: 2px; */
    color: black;
    display: inline-block;
}

.invisible-option {
    /* padding-left: 3px; */
    /* position: relative;
    top: 2px; */
    width: 0px !important;
    height: 0px;
    overflow: hidden;
    opacity: 0;
    /* color: white; */
    display: inline-block;
}
</style>