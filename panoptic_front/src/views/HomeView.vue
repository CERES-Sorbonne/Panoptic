<script setup lang="ts">
import Dropdown from '@/components/dropdowns/Dropdown.vue';
import Create from '@/components/home/Create.vue';
import Options from '@/components/home/Options.vue';
import { ModalId } from '@/data/models';
import { usePanopticStore } from '@/data/panopticStore';
import { useProjectStore } from '@/data/projectStore';
import router from '@/router';
import { computed, onMounted, reactive, ref } from 'vue';

const panoptic = usePanopticStore()
const store = useProjectStore()

interface Project {
    path: string
    name: string
}

const menuMode = ref(0) // 0 options 1 create
const hasProjects = computed(() => Array.isArray(panoptic.data.status.projects) && panoptic.data.status.projects.length > 0)

// use Unicode NON-BREAKING HYPHEN (U+2011)
// https://stackoverflow.com/questions/8753296/how-to-prevent-line-break-at-hyphens-in-all-browsers
function correctHyphen(path) {
    return path.replaceAll('-', '‑')
}

function createProject(project: { path: string, name: string }) {
    if (!project.path) return
    if (!project.name) return

    panoptic.createProject(project.path, project.name)
}

function importProject(path: string) {
    panoptic.importProject(path)
}

function delPlugin(path: string) {
    panoptic.delPlugin(path)
}

function promptPlugin() {
    panoptic.showModal(ModalId.FOLDERSELECTION, { mode: 'create', callback: panoptic.addPlugin })
}

onMounted(() => {
    if (panoptic.isProjectLoaded) {
        router.push('/view')
    }
})

</script>

<template>
    <div class="window d-flex">
        <div v-if="hasProjects" class="project-menu">
            <div v-for="project in panoptic.data.status.projects" class="d-flex">
                <div class="project flex-grow-1 overflow-hidden" @click="panoptic.loadProject(project.path)">
                    <h5 class="m-0">{{ project.name }}</h5>
                    <div class="m-0 p-0 text-wrap text-break dimmed-2" style="font-size: 13px;">{{
                        correctHyphen(project.path) }}</div>
                </div>
                <div class="project-option flex-shrink-0">
                    <Dropdown>
                        <template #button><i class="bi bi-three-dots-vertical"></i></template>
                        <template #popup="{ hide }">
                            <div class="text-start">
                                <div @click="panoptic.deleteProject(project.path); hide();" class="m-1 base-hover p-1"><i
                                        class="bi bi-trash me-1"></i>delete</div>
                                <!-- <div class="m-1 base-hover p-1"><i class="bi bi-pen me-1"></i>rename</div> -->
                            </div>
                        </template>
                    </Dropdown>

                </div>
            </div>
        </div>
        <div class="main-menu flex-grow-1">
            <div class="icon">👀</div>
            <h1 class="m-0 p-0">Panoptic</h1>
            <h6 class="dimmed-2">Version pre-2.0</h6>

            <div class="create-menu mt-5 pt-5">
                <Options v-if="menuMode == 0" @create="menuMode = 1" @import="importProject" />
                <Create v-if="menuMode == 1" @cancel="menuMode = 0" @create="createProject" />

                <div class="plugin-preview mt-5">
                    <h5 class="text-center">
                        Plugins
                        <span class="sb bi bi-plus" style="position: relative; top:1px" @click="promptPlugin"></span>
                    </h5>

                    <div v-for="path in panoptic.data.plugins" class="ps-1"><span @click="delPlugin(path)"
                            class="bi bi-x base-hover"></span> {{ path }}</div>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.dimmed-2 {
    color: rgb(90, 90, 90)
}

.nowrap {
    white-space: nowrap;
}

.window {
    width: 100vw;
    height: 100vh;
}

.project-menu {
    height: 100%;
    width: 350px;
    padding: 25px;
    padding-right: 0px;
    background-color: rgb(246, 246, 247);
    color: rgb(45, 45, 45);
    border-right: 1px solid var(--border-color);
    overflow-y: scroll;
}

.project {
    padding: 10px;
    cursor: pointer;
}

.project:hover {
    background-color: rgb(232, 232, 255);
    border-radius: 10px;
}


.main-menu {
    height: 100%;
    background-color: white;
    text-align: center;
    padding: 15px;
}

.project-option {
    width: 20px;
    margin: 0 15px;
    text-align: center;
    cursor: pointer;
}

.icon {
    font-size: 100px;
    line-height: 100px;
    margin-top: 50px;
}

.create-menu {
    /* background-color: green; */
    width: 500px;
    margin: auto;
}

.plugin-preview {
    /* position: absolute; */
    text-align: left;
    font-size: 13px;
    color: rgb(87, 87, 87)
}

.add-btn {
    padding: 4px;
    font-size: 15px;
    color: rgb(50, 50, 50);
}
</style>