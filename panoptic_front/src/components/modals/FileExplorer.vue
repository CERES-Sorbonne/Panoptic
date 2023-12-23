<script setup lang="ts">
import { ref, onMounted, onUpdated, computed, reactive } from 'vue';
import FileItem from './FileItem.vue';
import axios from 'axios'
import { apiGetFilesystemInfo, apiGetFilesystemLs } from '@/data/api';
import { DirInfo } from '@/data/models';
import FolderIcon from '../filesystem/FolderIcon.vue';


const fastList = reactive([] as DirInfo[])
const partitionList = reactive([] as DirInfo[])
const imageList = reactive([] as string[])
const openFolders = reactive([] as DirInfo[][])
const actualPath = ref('')

const scrollerElem = ref(null)

const baseRoot = computed(() => {
    if (openFolders.length == 0 || openFolders[0].length == 0) return '/'
    let path = openFolders[0][0].path
    path = path.slice(0, path.lastIndexOf('/') - 1)
    return path
})

async function updateInfo() {
    let { fast, partitions } = await apiGetFilesystemInfo()

    fastList.length = 0
    fastList.push(...fast)

    partitionList.length = 0
    partitionList.push(...partitions)
}

async function setOpenFolder(path) {
    let res = await apiGetFilesystemLs(path)
    console.log(res)
    openFolders.length = 0
    openFolders.push(res.directories)
    actualPath.value = path
    imageList.length = 0
    imageList.push(...res.images)
}

async function openSubFolder(path: string, folderIndex: number) {
    const res = await apiGetFilesystemLs(path)
    if (folderIndex < openFolders.length - 1) {
        openFolders.splice(folderIndex + 1)
    }
    openFolders.push(res.directories)
    actualPath.value = path
    imageList.length = 0
    imageList.push(...res.images)
}

onMounted(async () => {
    await updateInfo()
    setOpenFolder(fastList.filter(d => d.name == 'Home')[0].path)
});

onUpdated(() => {
    scrollerElem.value.scrollLeft = scrollerElem.value.scrollWidth;
});

</script>

<template>
    <div class="d-flex m-0 p-0  overflow-hidden rounded">
        <div class="dir-list p-3">
            <div>
                <div class="fs-title mb-1">{{ $t('modals.fs.fast') }}</div>
                <div v-for="dir in fastList">
                    <FolderIcon :dir="dir" :selected-path="actualPath" :base-root="baseRoot"
                        @click="setOpenFolder(dir.path)" />
                </div>
            </div>

            <div>
                <div class="fs-title mb-1">{{ $t('modals.fs.partitions') }}</div>
                <div v-for="dir in partitionList">
                    <FolderIcon :dir="dir" :selected-path="actualPath" :base-root="baseRoot"
                        @click="setOpenFolder(dir.path)" />
                </div>
            </div>
        </div>
        <div class="flex-grow-1" ref="explorerElem">
            <div class="d-flex">
                <div class="flex-grow-1 explorer-view overflow-scroll" ref="scrollerElem">
                    <div class="d-flex">
                        <div class="folder-list flex-shrink-0" v-for="folders, index in openFolders">
                            <div v-for="folder in folders">
                                <FolderIcon :dir="folder" :selected-path="actualPath" :base-root="baseRoot"
                                    @click="openSubFolder(folder.path, index)" />
                            </div>
                            <div v-if="folders.length == 0" class="text-secondary m-2">Empty</div>
                        </div>
                    </div>
                </div>

                <div class="image-list flex-shrink-0">
                    <!-- <span>Images</span> -->
                    <div v-for="img in imageList"><img :src="'http://localhost:8000/images/' + img" class="mini" />
                    </div>
                </div>
            </div>
            <div class="path d-flex">
                <div class="path-string flex-grow-1">{{ actualPath }}</div>
                <div class="open">Open</div>
            </div>

        </div>

    </div>
</template>
  
<style scoped>
.explorer-view {
    overflow: scroll;
    height: 75vh;
    width: calc(80vw - 400px);
    min-width: calc(80vw - 400px);
    border-right: 1px solid var(--border-color);
}

.path {
    border-top: 1px solid var(--border-color);
    /* border-bottom: 1px solid var(--border-color); */
}

.path-label {
    padding: 4px 6px;
    background-color: rgb(230, 230, 230);
}

.path-string {
    padding: 4px 6px;
    background-color: white;
}

.open {
    padding: 4px 6px;
    background-color: rgba(3, 99, 225, 0.464);
}

.folder-list {
    height: 75vh;
    overflow: scroll;
    padding-right: 5px;
    border-right: 1px solid var(--border-color);
}

.dir {
    padding: 2px 6px;
}

.dir-list {
    padding-right: 10px;
    min-width: 200px;
    max-width: 300px;
    overflow: hidden;
    text-wrap: nowrap;
    background-color: rgb(225, 226, 227);
}

.image-list {
    width: 150px;
    text-align: center;
    height: calc(75vh - 0px);
    overflow: scroll;
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
    overflow-y: scroll;
}

.mini {
    max-width: 100px;
    margin: 4px 0px;
}
</style>
 