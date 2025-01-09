<script setup lang="ts">
import Dropdown from '@/components/dropdowns/Dropdown.vue';
import Create from '@/components/home/Create.vue';
import Options from '@/components/home/Options.vue';
import { usePanopticStore } from '@/data/panopticStore';
import router from '@/router';
import { computed, nextTick, onMounted, ref } from 'vue';
import Tutorial from '@/tutorials/Tutorial.vue';
import Egg from '@/tutorials/Egg.vue';
import PluginForm from '@/components/forms/PluginForm.vue';
import PanopticIcon from '@/components/icons/PanopticIcon.vue';
import { ModalId } from '@/data/models';
import PluginOptionsDropdown from '@/components/dropdowns/PluginOptionsDropdown.vue';

const panoptic = usePanopticStore()

const menuMode = ref(0) // 0 options 1 create
const showPluginForm = ref(false)
const pluginFormElem = ref(null)
const show = ref(true)
const langs = ['fr', 'en']

const hasProjects = computed(() => Array.isArray(panoptic.data.status.projects) && panoptic.data.status.projects.length > 0)

const showFirstModal = computed(() => !hasProjects.value && panoptic.data.init)
const showTutorial = computed(() => !hasProjects.value && panoptic.data.init && panoptic.openModalId !== ModalId.FIRSTMODAL)

const hasPanopticMlPlugin = computed(() => panoptic.data.plugins.some(p => p.sourceUrl && p.sourceUrl.includes('https://github.com/CERES-Sorbonne/PanopticML')))

const usePlugins = computed(() => {
    const res = {}
    panoptic.data.status.projects.forEach(p => {
        res[p.path] = {}
        panoptic.data.plugins.forEach(pl => res[p.path][pl.name] = true)
        if (panoptic.data.status.ignoredPlugins[p.path]) {
            panoptic.data.status.ignoredPlugins[p.path].forEach(ig => {
                res[p.path][ig] = false
            })
        }
    })
    return res
})

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

async function loadDefaultPlugin() {
    showPluginForm.value = true
    await nextTick()
    pluginFormElem.value.setPanopticMl()
}

async function rerender() {
    show.value = false
    await nextTick()
    show.value = true
}

async function updateIgnorePlugin(a, b, c) {
    await panoptic.updateIgnorePlugin(a, b, !c)
}

onMounted(() => {
    if (panoptic.isProjectLoaded) {
        router.push('/view')
    }
    if (showFirstModal.value) {
        panoptic.showModal(ModalId.FIRSTMODAL)
    }
})

</script>

<template>
    <div v-if="show">
        <Egg />
        <Tutorial v-if="showTutorial" />

        <div class="window2 d-flex ">
            <div v-if="hasProjects" class="project-menu">
                <div v-for="project in panoptic.data.status.projects" class="d-flex">
                    <div class="project flex-grow-1 overflow-hidden" @click="panoptic.loadProject(project.path)">
                        <h5 class="m-0">{{ project.name }}</h5>
                        <div class="m-0 p-0 text-wrap text-break dimmed-2" style="font-size: 13px;">{{
                            correctHyphen(project.path) }}</div>
                    </div>
                    <div class="project-option flex-shrink-0">
                        <Dropdown>
                            <template #button>
                                <div style="position: relative; top: 10px;"><i class="bb bi bi-three-dots-vertical"></i>
                                </div>
                            </template>
                            <template #popup="{ hide }">
                                <div class="text-start p-1">
                                    <div @click="panoptic.deleteProject(project.path); hide();" class="bb">
                                        <i class="bi bi-trash me-1"></i>delete
                                    </div>
                                    <div style="border-top: 1px solid var(--border-color); width: 100%;" class="mt-1">
                                    </div>
                                    <div v-for="p in panoptic.data.plugins" class="mt-1">
                                        <input type="checkbox" class="me-1" :checked="usePlugins[project.path][p.name]"
                                            @change="e => updateIgnorePlugin(project.path, p.name, (e.target as any).checked)" />{{
                                        p.name }}
                                    </div>
                                    <!-- <div class="m-1 base-hover p-1"><i class="bi bi-pen me-1"></i>rename</div> -->
                                </div>
                            </template>
                        </Dropdown>

                    </div>
                </div>
            </div>
            <div v-if="panoptic.data.init" class="flex-grow-1">
                <div class="d-flex flex-column main-menu justify-content-center">
                    <div>
                        <div class="icon">
                            <PanopticIcon />
                        </div>
                        <h1 class="m-0 p-0">Panoptic</h1>
                        <h6 class="dimmed-2">Version 0.4</h6>
                        <div class="lang">
                            <i class="bi bi-translate" style="margin-right:0.5rem"></i>
                            <select v-model="$i18n.locale" @change="rerender">
                                <option v-for="(lang, i) in langs" :key="`Lang${i}`" :value="lang">
                                    {{ lang.toUpperCase() }}
                                </option>
                            </select>
                        </div>
                    </div>
                    <div id="main-menu" class="create-menu mt-5 pt-5">
                        <Options v-if="menuMode == 0" @create="menuMode = 1" @import="importProject" />
                        <Create v-if="menuMode == 1" @cancel="menuMode = 0" @create="createProject" />
                    </div>
                    <div class="mt-5 plugin-preview ">
                        <h5 class="text-center">
                            Plugins
                            <span class="sb bi bi-plus" style="position: relative; top:1px"
                                @click="showPluginForm = true"></span>
                        </h5>
                        <div v-if="!hasPanopticMlPlugin" class="text-center">
                            <span class="bb ms-1 me-1" @click="loadDefaultPlugin">
                                <i class="bi bi-lightbulb"></i>
                                {{ $t('main.home.plugins.install_panoptic_ml') }}
                            </span>
                        </div>
                    </div>
                    <div class="flex-grow-1 plugin-preview" style="overflow-y: auto;">
                        <PluginForm v-if="showPluginForm" @cancel="showPluginForm = false" ref="pluginFormElem" />
                        <div v-else>
                            <div v-for="plugin in panoptic.data.plugins" style="display: inline-block;">
                                <PluginOptionsDropdown :plugin="plugin"></PluginOptionsDropdown>
                            </div>
                        </div>
                    </div>

                </div>
            </div>
            <div v-else class="text-center mt-5 w-100">
                <p>Waiting for Server...</p>
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

.window2 {
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
    /* background-color: white; */
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
    font-size: 15px;
    color: rgb(87, 87, 87);
    /* height: 100%; */
    width: 500px;
    margin: auto;
}

.add-btn {
    padding: 4px;
    font-size: 15px;
    color: rgb(50, 50, 50);
}
</style>