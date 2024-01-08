<script setup lang="ts">
import { ref, onMounted, onUpdated, computed, reactive } from 'vue';

import { apiGetFilesystemInfo, apiGetFilesystemLs } from '@/data/api';
import { DirInfo } from '@/data/models';
import FolderItem from '../filesystem/FolderItem.vue';

const props = defineProps({
    mode: {
        type: String,
        default: "images"
    }
})

const emits = defineEmits({
    select: String
})

const fastList = reactive([] as DirInfo[])
const partitionList = reactive([] as DirInfo[])
const imageList = reactive([] as string[])
const openFolders = reactive([] as DirInfo[][])
const selectedFolder = ref({path: ""} as DirInfo)

const scrollerElem = ref(null)

const baseRoot = computed(() => {
    if (openFolders.length == 0 || openFolders[0].length == 0) return '/'
    let path = openFolders[0][0].path
    path = path.slice(0, path.lastIndexOf('/'))
    if (path == '') return '/'

    return path
})

const parents = computed(() => {
    const res = []
    let path = selectedFolder.value.path
    while (path.lastIndexOf('/') > 0) {
        path = path.slice(0, path.lastIndexOf('/'))
        if (path == '') {
            path = '/'
        }
        res.push(path)
    }
    return res
})

const isValidPath = computed(() => {
    if(props.mode === "images" && selectedFolder.value.images > 0){
        return true
    }
    else if(props.mode === "import" && selectedFolder.value.isProject){
        return true
    }
    else if(props.mode === "create" && !selectedFolder.value.isProject){
        return true
    }
    return false
})

async function updateInfo() {
    let { fast, partitions } = await apiGetFilesystemInfo()

    fastList.length = 0
    fastList.push(...fast)

    partitionList.length = 0
    partitionList.push(...partitions)
}

async function setOpenFolder(folder: DirInfo) {
    let res = await apiGetFilesystemLs(folder.path)
    // console.log(res.directories)
    openFolders.length = 0
    openFolders.push(res.directories.filter(d => !d.name.startsWith('.')))
    selectedFolder.value = folder
    imageList.length = 0
    imageList.push(...res.images)
}

async function openSubFolder(folder: DirInfo, folderIndex: number) {
    const res = await apiGetFilesystemLs(folder.path)
    if (folderIndex < openFolders.length - 1) {
        openFolders.splice(folderIndex + 1)
    }
    if (res.directories.length) openFolders.push(res.directories)
    selectedFolder.value = folder
    imageList.length = 0
    imageList.push(...res.images)
}

async function open() {
    if(!isValidPath.value){
        return false
    }
    emits('select', selectedFolder.value.path)
}


onMounted(async () => {
    await updateInfo()
    setOpenFolder(fastList.filter(d => d.name == 'Home')[0])
});

onUpdated(() => {
    scrollerElem.value.scrollLeft = scrollerElem.value.scrollWidth;
});

</script>

<template>
    <div class="d-flex m-0 p-0 bg-info" :style="{ width: '100%', height: '500px' }">
        <div class="dir-list">
            <div>
                <div class="fs-title mb-1">{{ $t('modals.fs.fast') }}</div>
                <div v-for="dir in fastList">
                    <FolderItem :dir="dir" :is-parent="baseRoot == dir.path" @click="setOpenFolder(dir)" />
                </div>
            </div>

            <div>
                <div class="fs-title mb-1">{{ $t('modals.fs.partitions') }}</div>
                <div v-for="dir in partitionList">
                    <FolderItem :dir="dir" :is-parent="baseRoot == dir.path" @click="setOpenFolder(dir)" />
                </div>
            </div>
        </div>
        <div class="flex-grow-1 d-flex flex-column">
            <div class="d-flex bg-warning flex-grow-1 overflow-hidden">
                <div class="folder-cols flex-grow-1 bg-white d-flex" ref="scrollerElem">
                    <div class="folder-list flex-shrink-0" v-for="folders, index in openFolders">
                        <div v-for="folder in folders" style="margin-bottom: 2px;">
                            <FolderItem :dir="folder" :is-parent="parents.includes(folder.path)" :light="true"
                                :selected="folder == selectedFolder" @click="openSubFolder(folder, index)" />
                        </div>
                        <!-- <div v-if="folders.length == 0" class="text-secondary m-2">Empty</div> -->
                    </div>
                </div>
                <div class="image-list flex-shrink-0 bg-white">
                    <div v-for="img in imageList">
                        <img :src="'http://localhost:8000/images/' + img" class="mini" />
                    </div>
                </div>
            </div>
            <div class="bg-success">
                <div class="path d-flex">
                    <div class="path-string flex-grow-1">{{ selectedFolder.path }}</div>
                    <div class="open flex-shrink-0" :class="{valid: isValidPath}" @click="open">{{ $t('modals.fs.open') }}</div>
                </div>
            </div>
        </div>


        <div>

        </div>

    </div>
</template>
  
<style scoped>
.folder-cols {
    overflow: auto;
    width: 200px;
}

.explorer-view {
    overflow: auto;
    height: 75vh;
    width: calc(80vw - 400px);
    min-width: calc(80vw - 400px);
    border-right: 1px solid var(--border-color);
}

.path {
    /* border-top: 1px solid var(--border-color); */
    /* border-bottom: 1px solid var(--border-color); */
}

.path-label {
    padding: 4px 6px;
    background-color: rgb(230, 230, 230);
    border-top: 1px solid var(--border-color);
}

.path-string {
    padding: 4px 6px;
    background-color: white;
    border-top: 1px solid var(--border-color);
}

.open {
    padding: 4px 6px;
    /* background-color: rgb(225, 226, 227); */
    background-color: rgb(142, 148, 156);
    
    color: white;
    cursor: pointer;
    border-bottom-right-radius: 5px;
}

.valid{
    background-color: rgb(73, 134, 213);
}

.open .valid:hover {
    background-color: rgb(3, 100, 225);
}

.folder-list {
    overflow: auto;
    padding: 5px;
    border-right: 1px solid var(--border-color);
}

.dir-list {
    padding: 10px;
    width: 200px;
    overflow: hidden;
    text-wrap: nowrap;
    white-space: nowrap;
    background-color: rgb(225, 226, 227);
    box-shadow: 0px 0px 3px 1px var(--border-color);
    z-index: 2;
}

.image-list {
    background-color: #c3cfd9;
    width: 120px;
    text-align: center;
    overflow-y: auto;
    overflow-x: hidden;
    /* border-left: 1px solid var(--border-color); */
    box-shadow: 0px 0px 3px 1px var(--border-color);
}

.fs-title {
    color: grey;
    font-size: 12px;
}

.header {
    background-color: #c3cfd9 !important;
    color: rgb(50, 50, 50);
}

.images {
    max-height: 75vh;
    overflow-y: auto;
}

.mini {
    max-width: 100px;
    margin: 4px 0px;
}
</style>
 