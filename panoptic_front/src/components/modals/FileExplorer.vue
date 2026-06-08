<script setup lang="ts">
import { ref, onMounted, computed, reactive, nextTick } from 'vue';

import { apiGetFilesystemCount, apiGetFilesystemInfo, apiGetFilesystemLs, SERVER_PREFIX } from '@/data/apiPanopticRoutes';
import { DirInfo } from '@/data/models';
import FolderItem from '../filesystem/FolderItem.vue';
import { goNext } from '@/utils/utils';

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
const selectedFolder = ref({ path: "" } as DirInfo)
const selectedFullCount = ref(null)
const scrollerElem = ref(null)
const isCounting = ref(false)

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
    if (props.mode === "images") {
        return true
    }
    else if (props.mode === "import" && selectedFolder.value.isProject) {
        return true
    }
    else if (props.mode === "create" && !selectedFolder.value.isProject) {
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

// Keep the newly opened (right-most) column in view.
function scrollToEnd() {
    nextTick(() => {
        if (scrollerElem.value) scrollerElem.value.scrollLeft = scrollerElem.value.scrollWidth
    })
}

async function setOpenFolder(folder: DirInfo) {
    let res = await apiGetFilesystemLs(folder.path)
    res.directories.sort((a, b) => a.name.localeCompare(b.name))
    // console.log(res.directories)
    openFolders.length = 0
    openFolders.push(res.directories.filter(d => !d.name.startsWith('.')))
    selectedFolder.value = folder
    imageList.length = 0
    imageList.push(...res.images)
    selectedFullCount.value = null
    isCounting.value = false
    scrollToEnd()
}

async function openSubFolder(folder: DirInfo, folderIndex: number) {
    const res = await apiGetFilesystemLs(folder.path)
    res.directories.sort((a, b) => a.name.localeCompare(b.name))
    if (folderIndex < openFolders.length - 1) {
        openFolders.splice(folderIndex + 1)
    }
    if (res.directories.length) openFolders.push(res.directories)
    selectedFolder.value = folder
    imageList.length = 0
    imageList.push(...res.images)
    selectedFullCount.value = null
    isCounting.value = false
    scrollToEnd()
}

async function open() {
    if (!isValidPath.value) {
        return false
    }
    emits('select', selectedFolder.value.path)
    goNext()
}

async function count() {
    if (isCounting.value || selectedFullCount.value != null) return
    isCounting.value = true
    const res = await apiGetFilesystemCount(selectedFolder.value.path)
    if (res.path == selectedFolder.value.path) {
        selectedFullCount.value = res.count
    }
    isCounting.value = false
}


onMounted(async () => {
    await updateInfo()
    setOpenFolder(fastList.filter(d => d.name == 'Home')[0])
});

</script>

<template>
    <div class="file-explorer">
        <!-- Left: quick access + partitions -->
        <div class="dir-list">
            <div class="fs-title">{{ $t('modals.fs.fast') }}</div>
            <div v-for="dir in fastList" :key="dir.path">
                <FolderItem :dir="dir" :is-parent="baseRoot == dir.path" @click="setOpenFolder(dir)" />
            </div>

            <div class="fs-title fs-title-spaced">{{ $t('modals.fs.partitions') }}</div>
            <div v-for="dir in partitionList" :key="dir.path">
                <FolderItem :dir="dir" :is-parent="baseRoot == dir.path" @click="setOpenFolder(dir)" />
            </div>
        </div>

        <!-- Right: folder columns + image preview + pinned action bar -->
        <div class="explorer-main">
            <div class="explorer-body">
                <div class="folder-cols" ref="scrollerElem">
                    <div class="folder-list" v-for="folders, index in openFolders" :key="index">
                        <div v-for="folder in folders" :key="folder.path" class="folder-row">
                            <FolderItem :dir="folder" :is-parent="parents.includes(folder.path)" :light="true"
                                :selected="folder == selectedFolder" @click="openSubFolder(folder, index)" />
                        </div>
                    </div>
                </div>
                <div v-if="imageList.length" class="image-list">
                    <img v-for="img in imageList" :key="img" :src="SERVER_PREFIX + '/images/' + img" class="mini" />
                </div>
            </div>

            <div class="action-bar">
                <div class="path-string">{{ selectedFolder.path }}</div>
                <div class="count" @click="count">
                    <span v-if="selectedFullCount != null">{{ selectedFullCount }} images</span>
                    <span v-else-if="!isCounting">Count</span>
                    <span v-else class="spinner-border spinner-border-sm" role="status" />
                </div>
                <div id="confirm-modal" class="open" :class="{ valid: isValidPath }" @click="open">
                    {{ $t('modals.fs.open') }}
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
/* Root: fills the modal body; flex row of [sidebar | main]. */
.file-explorer {
    display: flex;
    width: 100%;
    height: 100%;
    min-height: 0;
    background-color: var(--island-surface);
    font-size: var(--font-size-sm);
    color: var(--text-primary);
}

/* ── Left sidebar: quick access + partitions ─────────────────────────── */
.dir-list {
    flex-shrink: 0;
    width: 200px;
    padding: var(--spacing-sm);
    overflow-y: auto;
    white-space: nowrap;
    background-color: var(--bg-secondary);
    border-right: 1px solid var(--border-color);
}

.fs-title {
    color: var(--text-tertiary);
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-semibold);
    text-transform: uppercase;
    letter-spacing: 0.02em;
    margin-bottom: 4px;
}

.fs-title-spaced {
    margin-top: var(--spacing-md);
}

/* ── Right main area: body (scrolls) + pinned action bar ─────────────── */
.explorer-main {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    min-height: 0;
}

.explorer-body {
    flex: 1;
    min-height: 0;
    display: flex;
    overflow: hidden;
}

.folder-cols {
    flex: 1;
    min-width: 0;
    display: flex;
    overflow-x: auto;
    overflow-y: hidden;
    background-color: var(--island-surface);
}

.folder-list {
    flex-shrink: 0;
    min-width: 160px;
    overflow-y: auto;
    padding: var(--spacing-xs);
    border-right: 1px solid var(--border-light);
}

.folder-row {
    margin-bottom: 2px;
}

.image-list {
    flex-shrink: 0;
    width: 120px;
    overflow-y: auto;
    overflow-x: hidden;
    text-align: center;
    background-color: var(--bg-secondary);
    border-left: 1px solid var(--border-color);
}

.mini {
    max-width: 100px;
    margin: 4px 0;
    border-radius: var(--radius-sm);
}

/* ── Action bar: always visible, even on short windows ───────────────── */
.action-bar {
    flex-shrink: 0;
    display: flex;
    align-items: stretch;
    border-top: 1px solid var(--border-color);
    background-color: var(--bg-secondary);
}

.path-string {
    flex: 1;
    min-width: 0;
    display: flex;
    align-items: center;
    padding: 6px 10px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--text-secondary);
    font-family: var(--font-mono);
    font-size: var(--font-size-xs);
}

.count {
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    min-width: 80px;
    padding: 6px 10px;
    cursor: pointer;
    color: var(--text-secondary);
    border-left: 1px solid var(--border-color);
}

.count:hover {
    background-color: var(--hover-bg);
    color: var(--text-primary);
}

.open {
    display: flex;
    align-items: center;
    flex-shrink: 0;
    padding: 6px 18px;
    cursor: pointer;
    color: var(--text-tertiary);
    background-color: var(--bg-tertiary);
    border-left: 1px solid var(--border-color);
    font-weight: var(--font-weight-medium);
    transition: background-color var(--transition-fast);
}

.open.valid {
    background-color: var(--primary);
    color: var(--text-inverse);
}

.open.valid:hover {
    background-color: var(--primary-dark);
}
</style>