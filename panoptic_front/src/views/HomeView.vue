<script setup lang="ts">
import Create from '@/components/home/Create.vue';
import Options from '@/components/home/Options.vue';
import { usePanopticStore } from '@/data/stores/panopticStore';
import { computed, nextTick, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import Tutorial from '@/tutorials/Tutorial.vue';
import Egg from '@/tutorials/Egg.vue';
import PluginForm from '@/components/forms/PluginForm.vue';
import PanopticIcon from '@/components/icons/PanopticIcon.vue';
import { ModalId, PluginType, ProjectRef } from '@/data/models';
import wTT from "@/components/tooltips/withToolTip.vue";
import Dropdown from '@/components/dropdowns/Dropdown.vue';
import PluginOptionsDropdown from '@/components/dropdowns/PluginOptionsDropdown.vue';
import UserSelector from '@/components/home/UserSelector.vue';
import FolderSelectionModal from '@/components/modals/FolderSelectionModal.vue';
import FirstModal from '@/components/modals/FirstModal.vue';
import NotifModal from '@/components/modals/NotifModal.vue';
import LegacyImportModal from '@/components/modals/LegacyImportModal.vue';

const panoptic = usePanopticStore()
const { t } = useI18n()

const menuMode = ref(0) // 0 options 1 create
const showPluginForm = ref(false)
const pluginFormElem = ref(null)
const show = ref(true)
const langs = ['fr', 'en']

const hasProjects = computed(() => panoptic.projects.length > 0)
// Seuls les projets compatibles s'ouvrent. Les autres sont listés grisés en dessous,
// avec un bouton de conversion quand c'est possible.
const sortedProjects = computed(() => [
    ...panoptic.projects.filter(p => isCompatible(p)),
    ...panoptic.projects.filter(p => !isCompatible(p)),
])
// Projets 0.x trouvés par le scan: grisés eux aussi, convertis via LegacyImportModal
const legacyProjects = computed(() => panoptic.hasLegacyProjects ? panoptic.legacyProjects : [])
const showProjectMenu = computed(() => hasProjects.value || legacyProjects.value.length > 0)

// Cas classique de mise à jour: aucun projet récent mais plusieurs anciens.
// La proposition de migration passe donc avant FirstModal et le tutoriel.
const hasLegacyProjects = computed(() => panoptic.hasLegacyProjects)
const showFirstModal = computed(() => !hasProjects.value && !hasLegacyProjects.value)
const showTutorial = computed(() => !hasProjects.value && !hasLegacyProjects.value && panoptic.openModalId !== ModalId.FIRSTMODAL)

const hasPanopticMlPlugin = computed(() => panoptic.plugins.some(p => p.sourceType == PluginType.PIP && p.sourcePath == 'panopticml'))

const usePlugins = computed(() => {
    const res = {}
    panoptic.projects.forEach(project => {
        res[project.id] = {}
        panoptic.plugins.forEach(plugin => res[project.id][plugin.id] = true)
        project.excludedPlugins.forEach(pId => res[project.id][pId] = false)
    })
    return res
})

function isCompatible(project: ProjectRef) {
    return !project.status || project.status == 'ok'
}

function openProject(project: ProjectRef) {
    if (!isCompatible(project)) return
    panoptic.loadProject(project.id)
}

async function convertProject(project: ProjectRef) {
    if (!window.confirm(t('main.home.convert.confirm', { name: project.name }))) return
    await panoptic.convertProject(project.id)
}

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

async function updateIgnorePlugin(project: ProjectRef, pluginName: string, value: boolean) {
    if (!value && !project.excludedPlugins.includes(pluginName)) {
        project.excludedPlugins.push(pluginName)
    } else if (value && project.excludedPlugins.includes(pluginName)) {
        project.excludedPlugins = project.excludedPlugins.filter(n => n !== pluginName)
    }
    await panoptic.updateProject(project)
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

// Le scan des anciens projets arrive de façon asynchrone: on attend son résultat
// avant de décider quelle intro afficher, sinon FirstModal gagne la course.
// La modale de conversion ne s'ouvre jamais seule, uniquement via la bannière.
watch(() => [panoptic.projectsLoaded, panoptic.legacyScanLoaded, hasLegacyProjects.value], () => {
    if (!panoptic.projectsLoaded || !panoptic.legacyScanLoaded) return
    if (hasLegacyProjects.value) {
        if (panoptic.openModalId === ModalId.FIRSTMODAL) panoptic.hideModal(ModalId.FIRSTMODAL)
        panoptic.introShown = true
        return
    }
    if (panoptic.introShown) return
    panoptic.introShown = true
    if (showFirstModal.value) {
        panoptic.showModal(ModalId.FIRSTMODAL)
    }
}, { immediate: true })

function openLegacyModal(legacyPath?: string) {
    panoptic.showModal(ModalId.LEGACY, legacyPath ? { legacyPath } : undefined)
}

</script>

<template>
    <div v-if="show">
        <Egg />
        <Tutorial v-if="showTutorial" />

        <FolderSelectionModal :id="ModalId.FOLDERSELECTION" />
        <FirstModal />
        <LegacyImportModal />
        <NotifModal />

        <div class="window2 d-flex ">
            <div v-if="showProjectMenu" class="project-menu">
                <div v-for="project in sortedProjects" :key="project.id" class="d-flex"
                    :class="{ 'old-project': !isCompatible(project) }">
                    <div class="project flex-grow-1 overflow-hidden" @click="openProject(project)"
                        :title="project.problem ?? ''">
                        <h5 class="m-0">{{ project.name }}</h5>
                        <div class="m-0 p-0 text-wrap text-break dimmed-2" style="font-size: 13px;">{{
                            correctHyphen(project.path) }}</div>
                        <template v-if="!isCompatible(project)">
                            <div style="font-size: 12px;">{{ $t('main.home.convert.' + project.status) }}</div>
                            <span v-if="project.status == 'outdated'" class="legacy-banner-btn legacy-convert"
                                :class="{ converting: panoptic.convertingProjects.includes(project.id) }"
                                @click.stop="convertProject(project)">
                                <template v-if="panoptic.convertingProjects.includes(project.id)">
                                    <i class="bi bi-hourglass-split me-1"></i>{{ $t('main.home.convert.running') }}
                                </template>
                                <template v-else>{{ $t('main.home.legacy.banner_button') }}</template>
                            </span>
                        </template>
                    </div>
                    <div class="project-option flex-shrink-0">
                        <Dropdown>
                            <template #button>
                                <div style="position: relative; top: 10px;"><i class="bb bi bi-three-dots-vertical"></i>
                                </div>
                            </template>
                            <template #popup="{ hide }">
                                <div class="text-start p-1">
                                    <div @click="panoptic.deleteProject(project.id);" class="bb">
                                        <i class="bi bi-trash me-1"></i>delete
                                    </div>
                                    <div style="border-top: 1px solid var(--border-color); width: 100%;" class="mt-1">
                                    </div>
                                    <div v-for="p in panoptic.plugins" class="mt-1">
                                        <input type="checkbox" class="me-1" :checked="usePlugins[project.id][p.id]"
                                            @change="e => updateIgnorePlugin(project, p.id, (e.target as any).checked)" />{{
                                                p.id }}
                                    </div>
                                    <!-- <div class="m-1 base-hover p-1"><i class="bi bi-pen me-1"></i>rename</div> -->
                                </div>
                            </template>
                        </Dropdown>

                    </div>
                </div>
                <div v-for="project in legacyProjects" :key="project.legacyPath" class="d-flex legacy-project">
                    <div class="flex-grow-1 overflow-hidden">
                        <h5 class="m-0">{{ project.name }}</h5>
                        <div class="m-0 p-0 text-wrap text-break" style="font-size: 13px;">{{
                            correctHyphen(project.legacyPath) }}</div>
                        <div style="font-size: 12px;">{{ $t('main.home.convert.outdated') }}</div>
                    </div>
                    <div class="flex-shrink-0 align-self-center">
                        <span class="legacy-banner-btn legacy-convert" @click="openLegacyModal(project.legacyPath)">
                            {{ $t('main.home.legacy.banner_button') }}
                        </span>
                    </div>
                </div>
            </div>
            <div class="flex-grow-1 d-flex flex-column overflow-hidden">
                <div v-if="hasLegacyProjects" class="legacy-banner" @click="openLegacyModal()">
                    <i class="bi bi-box-arrow-in-down me-1"></i>
                    <b>{{ $t('main.home.legacy.banner', { count: panoptic.legacyProjects.length }) }}</b>
                    <span class="legacy-banner-btn ms-2">{{ $t('main.home.legacy.banner_button') }}</span>
                </div>
                <div class="d-flex flex-column main-menu justify-content-center">
                    <div>
                        <div class="icon">
                            <PanopticIcon />
                        </div>
                        <h1 class="m-0 p-0">Panoptic</h1>
                        <div class="d-flex justify-content-center gap-1">
                            <h6 class="dimmed-2 mt-1">Version {{ panoptic.version }} </h6>
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
                            <div v-for="plugin in panoptic.plugins" style="display: inline-block;">
                                <PluginOptionsDropdown :plugin="plugin"></PluginOptionsDropdown>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="user-section">
                    <UserSelector />
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
    flex: 1;
    min-height: 0;
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

.user-section {
    flex-shrink: 0;
    width: 500px;
    margin: 0 auto;
    border-top: 1px solid var(--border-color);
}

.legacy-banner {
    background-color: rgb(238, 238, 255);
    border-bottom: 1px solid var(--border-color);
    padding: 10px 15px;
    text-align: left;
    cursor: pointer;
    color: rgb(45, 45, 45);
}

.old-project .project {
    cursor: default;
    color: rgb(150, 150, 150);
}

.old-project .project:hover {
    background-color: transparent;
}

.old-project .legacy-convert {
    display: inline-block;
    margin-top: 4px;
}

.legacy-convert.converting {
    background-color: rgb(200, 200, 200);
    cursor: default;
}

.legacy-project {
    padding: 10px;
    margin-right: 15px;
    color: rgb(150, 150, 150);
}

.legacy-convert {
    cursor: pointer;
    white-space: nowrap;
}

.legacy-banner-btn {
    background-color: rgb(170, 170, 255);
    color: white;
    border-radius: 8px;
    padding: 2px 8px;
}
</style>