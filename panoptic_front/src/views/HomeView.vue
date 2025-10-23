<script setup lang="ts">
import Create from '@/components/home/Create.vue';
import Options from '@/components/home/Options.vue';
import { usePanopticStore } from '@/data/panopticStore';
import router from '@/router';
import { computed, nextTick, onMounted, ref } from 'vue';
import Tutorial from '@/tutorials/Tutorial.vue';
import Egg from '@/tutorials/Egg.vue';
import PluginForm from '@/components/forms/PluginForm.vue';
import PanopticIcon from '@/components/icons/PanopticIcon.vue';
import { ModalId, PluginType } from '@/data/models';
import wTT from "@/components/tooltips/withToolTip.vue";
import Dropdown from '@/components/Dropdowns/Dropdown.vue';
import PluginOptionsDropdown from '@/components/Dropdowns/PluginOptionsDropdown.vue';

const panoptic = usePanopticStore()

const menuMode = ref(0) // 0 options 1 create
const showPluginForm = ref(false)
const pluginFormElem = ref(null)
const show = ref(true)
const langs = ['fr', 'en']

const hasProjects = computed(() => Array.isArray(panoptic.serverState.projects) && panoptic.serverState.projects.length > 0)

const showFirstModal = computed(() => !hasProjects.value)
const showTutorial = computed(() => !hasProjects.value && panoptic.openModalId !== ModalId.FIRSTMODAL)

const hasPanopticMlPlugin = computed(() => panoptic.serverState.plugins.some(p => p.type == PluginType.PIP && p.source == 'panopticml'))

const usePlugins = computed(() => {
    const res = {}
    const projects = panoptic.serverState.projects
    const plugins = panoptic.serverState.plugins
    projects.forEach(project => {
        res[project.id] = {}
        plugins.forEach(plugin => res[project.id][plugin.name] = true)
        project.ignoredPlugins.forEach(pId => res[project.id][pId] = false)
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

async function downloadPackagesInfos() {
    try {
        const data = await panoptic.getPackagesInfo();
        const jsonData = JSON.stringify(data, null, 2);
        const blob = new Blob([jsonData], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = 'panoptic_infos.json';
        link.click();
        URL.revokeObjectURL(url);
    } catch (error) {
        console.error('Erreur lors de la récupération ou du téléchargement des données :', error);
    }
}

onMounted(() => {
    if (panoptic.isProjectLoaded) {
        router.push('/view')
    }
    if (showFirstModal.value) {
        panoptic.showModal(ModalId.FIRSTMODAL)
    }
})

function createTestProject() {
    panoptic.createProject('/Users/david/panoptic-projects', 'test-' + Math.floor(performance.now() / 1000))
}

</script>

<template>
    <div v-if="show">
        <Egg />
        <Tutorial v-if="showTutorial" />

        <div class="window2 d-flex ">
            <div v-if="hasProjects" class="project-menu">
                <div v-for="project in panoptic.serverState.projects" class="d-flex">
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
                                    <div @click="panoptic.deleteProject(project.path);" class="bb">
                                        <i class="bi bi-trash me-1"></i>delete
                                    </div>
                                    <div style="border-top: 1px solid var(--border-color); width: 100%;" class="mt-1">
                                    </div>
                                    <div v-for="p in panoptic.serverState.plugins" class="mt-1">
                                        <input type="checkbox" class="me-1" :checked="usePlugins[project.id][p.name]"
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
            <div class="flex-grow-1">
                <div class="d-flex flex-column main-menu justify-content-center">
                    <div>
                        <div class="icon">
                            <PanopticIcon />
                        </div>
                        <h1 class="m-0 p-0">Panoptic</h1>
                        <div class="d-flex justify-content-center gap-1">
                            <h6 class="dimmed-2 mt-1">Version {{ panoptic.serverState.version }} </h6>
                            <wTT message='main.home.version_tooltip'><i class="bb bi-bug" style="margin-right:0.5rem"
                                    @click="downloadPackagesInfos"></i></wTT>
                        </div>
                        <div class="lang">
                            <i class="bi bi-translate" style="margin-right:0.5rem"></i>
                            <select v-model="$i18n.locale" @change="rerender">
                                <option v-for="(lang, i) in langs" :key="`Lang${i}`" :value="lang">
                                    {{ lang.toUpperCase() }}
                                </option>
                            </select>
                        </div>
                    </div>
                    <div class="bb" @click="createTestProject">Test-Project</div>
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
                            <div v-for="plugin in panoptic.serverState.plugins" style="display: inline-block;">
                                <PluginOptionsDropdown :plugin="plugin"></PluginOptionsDropdown>
                            </div>
                        </div>
                    </div>

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