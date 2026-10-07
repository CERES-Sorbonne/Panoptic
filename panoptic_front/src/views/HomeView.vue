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
import { LegacyMigrationRun, LegacyProject, ModalId, PluginType, ProjectRef } from '@/data/models';
import wTT from "@/components/tooltips/withToolTip.vue";
import Dropdown from '@/components/dropdowns/Dropdown.vue';
import PluginOptionsDropdown from '@/components/dropdowns/PluginOptionsDropdown.vue';
import UserSelector from '@/components/home/UserSelector.vue';
import FolderSelectionModal from '@/components/modals/FolderSelectionModal.vue';
import FirstModal from '@/components/modals/FirstModal.vue';
import NotifModal from '@/components/modals/NotifModal.vue';
import TauriDbSelector from '@/components/tauri/TauriDbSelector.vue';
import { isTauri } from '@/data/tauriLauncherStore';

const panoptic = usePanopticStore()
// shown when the backend cannot be reached; empty means same origin
const backendUrl = (import.meta as any).env.VITE_API_ROUTE || window.location.origin
const { t, te } = useI18n()

const menuMode = ref(0) // 0 options 1 create
const showPluginForm = ref(false)
const pluginFormElem = ref(null)
const show = ref(true)
const langs = ['fr', 'en']

const hasProjects = computed(() => panoptic.projects.length > 0)
// Seuls les projets compatibles s'ouvrent. Les autres sont listés grisés en dessous,
// avec un bouton de conversion quand c'est possible.
// Le groupe d'un projet est fixé la première fois qu'on le voit: un projet converti
// reste à sa place au lieu de sauter en haut de la liste.
const firstSeenCompatible = new Map<string | number, boolean>()
function listedAsCompatible(project: ProjectRef) {
    if (!firstSeenCompatible.has(project.id)) firstSeenCompatible.set(project.id, isCompatible(project))
    return firstSeenCompatible.get(project.id)
}
const sortedProjects = computed(() => [
    ...panoptic.projects.filter(p => listedAsCompatible(p)),
    ...panoptic.projects.filter(p => !listedAsCompatible(p)),
])
// Projets 0.x trouvés par le scan: grisés eux aussi, convertis directement depuis leur ligne
const legacyProjects = computed(() => panoptic.hasLegacyProjects ? panoptic.legacyProjects : [])
const isProjectListEmpty = computed(() => panoptic.projectsLoaded && panoptic.legacyScanLoaded
    && !hasProjects.value && !legacyProjects.value.length)

// Progression de la migration 0.x en cours, affichée sur la ligne du projet concerné.
// Le backend signale une étape quand elle se termine: stageIndex compte les étapes finies,
// l'étape en cours est donc la suivante dans le pipeline (même ordre que le backend).
const LEGACY_STAGES = ['read-legacy', 'write-data-db', 'write-media-db', 'write-project-db', 'check', 'register-project']
function legacyRun(project: LegacyProject) {
    const run = panoptic.legacyMigration
    return run?.legacyPath == project.legacyPath ? run : undefined
}
function runProgress(run: LegacyMigrationRun) {
    if (run.status == 'done') return 100
    if (!run.stageCount) return 0
    return run.stageIndex / run.stageCount * 100
}
function runCurrentStep(run: LegacyMigrationRun) {
    return Math.min(run.stageIndex + 1, run.stageCount)
}
function runStageLabel(run: LegacyMigrationRun) {
    const stage = LEGACY_STAGES[run.stageIndex]
    const key = 'modals.legacy.stages.' + stage
    return stage && te(key) ? t(key) : t('main.home.convert.running')
}

function canMigrate(project: LegacyProject) {
    return project.exists && !!project.shape && !project.migratedTo
}

// Refus du backend avant le démarrage (destination non vide, ...), par projet
const legacyErrors = ref<{ [legacyPath: string]: string }>({})
function legacyError(project: LegacyProject) {
    const run = legacyRun(project)
    return legacyErrors.value[project.legacyPath] ?? (run?.status == 'failed' ? (run.error || ' ') : undefined)
}

// Conversion directe vers le dossier proposé: le projet d'origine n'est jamais modifié
async function migrateLegacy(project: LegacyProject) {
    if (panoptic.isMigrationRunning) return
    const dest = project.suggestedPath
    if (!window.confirm(t('main.home.legacy.confirm', { name: project.name, dest }))) return
    delete legacyErrors.value[project.legacyPath]
    try {
        await panoptic.migrateLegacyProject(project.legacyPath, dest, project.name, false)
    } catch (e: any) {
        legacyErrors.value[project.legacyPath] = e?.response?.data?.message ?? e?.message ?? ' '
    }
}

// Cas classique de mise à jour: aucun projet récent mais plusieurs anciens.
// La proposition de migration passe donc avant FirstModal et le tutoriel.
const hasLegacyProjects = computed(() => panoptic.hasLegacyProjects)
const showFirstModal = computed(() => !hasProjects.value && !hasLegacyProjects.value)
// the backend must have answered first: before that "no project" only means "not loaded yet"
const showTutorial = computed(() => panoptic.isConnected && panoptic.projectsLoaded && !hasProjects.value && !hasLegacyProjects.value && panoptic.openModalId !== ModalId.FIRSTMODAL)

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
watch(() => [panoptic.isConnected, panoptic.projectsLoaded, panoptic.legacyScanLoaded, hasLegacyProjects.value], () => {
    if (!panoptic.isConnected || !panoptic.projectsLoaded || !panoptic.legacyScanLoaded) return
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

</script>

<template>
    <div v-if="show">
        <Egg />
        <Tutorial v-if="showTutorial" />

        <FolderSelectionModal :id="ModalId.FOLDERSELECTION" />
        <FirstModal />
        <NotifModal />

        <div class="window2 d-flex ">
            <!-- Toujours rendue, même vide: la colonne n'apparaît pas en cours de route
                 et ne décale pas le menu principal -->
            <div class="project-menu">
                <div v-if="isProjectListEmpty" class="dimmed-2 project-empty">{{ $t('main.home.no_projects') }}</div>
                <div v-for="project in sortedProjects" :key="project.id" class="d-flex"
                    :class="{ 'old-project': !isCompatible(project) }">
                    <div class="project flex-grow-1 overflow-hidden" @click="openProject(project)"
                        :title="project.problem ?? ''">
                        <h5 class="m-0">{{ project.name }}</h5>
                        <div class="m-0 p-0 text-wrap text-break dimmed-2" style="font-size: 13px;">{{
                            correctHyphen(project.path) }}</div>
                        <template v-if="!isCompatible(project)">
                            <div style="font-size: 12px;">{{ $t('main.home.convert.' + project.status) }}</div>
                            <!-- hauteur fixe: bouton et progression occupent la même place -->
                            <div v-if="project.status == 'outdated'" class="convert-slot">
                                <template v-if="panoptic.convertingProjects.includes(project.id)">
                                    <div class="convert-label">{{ $t('main.home.convert.running') }}</div>
                                    <div class="convert-bar indeterminate"><div></div></div>
                                </template>
                                <span v-else class="convert-btn" @click.stop="convertProject(project)">
                                    {{ $t('main.home.legacy.banner_button') }}
                                </span>
                            </div>
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
                <template v-if="legacyProjects.length">
                    <div class="legacy-section">{{ $t('main.home.legacy.section') }}</div>
                    <div v-for="project in legacyProjects" :key="project.legacyPath" class="legacy-project">
                        <h5 class="m-0">{{ project.name }}</h5>
                        <div class="m-0 p-0 text-wrap text-break" style="font-size: 13px;">{{
                            correctHyphen(project.legacyPath) }}</div>
                        <div v-if="!canMigrate(project)" style="font-size: 12px;">
                            <wTT :message="project.problem">{{ $t('modals.legacy.unavailable') }}</wTT>
                        </div>
                        <div v-if="canMigrate(project)" class="convert-slot">
                            <template v-if="legacyError(project)">
                                <div class="convert-label failed">
                                    <span class="text-truncate"><wTT :message="legacyError(project)">
                                        <i class="bi bi-exclamation-triangle me-1"></i>{{ $t('main.home.legacy.failed') }}
                                    </wTT></span>
                                    <span class="bb flex-shrink-0" @click="migrateLegacy(project)">
                                        {{ $t('main.home.legacy.retry') }}</span>
                                </div>
                            </template>
                            <template v-else-if="legacyRun(project)">
                                <div class="convert-label">
                                    <span class="text-truncate">{{ legacyRun(project).status == 'done'
                                        ? $t('main.home.legacy.done') : runStageLabel(legacyRun(project)) }}</span>
                                    <span v-if="legacyRun(project).stageCount" class="num flex-shrink-0">{{
                                        runCurrentStep(legacyRun(project)) }}/{{ legacyRun(project).stageCount }}</span>
                                </div>
                                <div class="convert-bar"><div :style="{ width: runProgress(legacyRun(project)) + '%' }"></div></div>
                            </template>
                            <span v-else class="convert-btn" :class="{ disabled: panoptic.isMigrationRunning }"
                                @click="migrateLegacy(project)">
                                {{ $t('main.home.legacy.banner_button') }}
                            </span>
                        </div>
                    </div>
                </template>
            </div>
            <div class="flex-grow-1 d-flex flex-column overflow-hidden">
                <div class="d-flex flex-column main-menu justify-content-center">
                    <div>
                        <div class="icon">
                            <PanopticIcon />
                        </div>
                        <h1 class="m-0 p-0">Panoptic</h1>
                        <!-- rendu même hors connexion pour réserver la hauteur de la ligne -->
                        <div class="d-flex justify-content-center gap-1"
                            :style="{ visibility: panoptic.isConnected ? 'visible' : 'hidden' }">
                            <h6 class="dimmed-2 mt-1">Version <span class="num">{{ panoptic.version }}</span> </h6>
                            <wTT message='main.home.version_tooltip'><i class="bb bi-bug" style="margin-right:0.5rem"
                                    @click="downloadPackagesInfos"></i></wTT>
                        </div>
                        <TauriDbSelector v-if="isTauri && panoptic.isConnected" confirm class="mt-2" />
                        <div class="lang">
                            <i class="bi bi-translate" style="margin-right:0.5rem"></i>
                            <select v-model="$i18n.locale" @change="rerender">
                                <option v-for="(lang, i) in langs" :key="`Lang${i}`" :value="lang">
                                    {{ lang.toUpperCase() }}
                                </option>
                            </select>
                        </div>
                    </div>
                    <div v-if="!panoptic.isConnected" class="backend-status mt-5 pt-5 text-center">
                        <template v-if="panoptic.failedConnected">
                            <i class="bi bi-exclamation-triangle text-danger me-1"></i>
                            {{ $t('main.home.backend.failed') }}
                            <div class="dimmed-2 mt-1" style="font-size: 12px;">{{ backendUrl }}</div>
                        </template>
                        <template v-else>
                            <span class="spinner-border spinner-border-sm text-secondary me-2" role="status" aria-hidden="true"></span>
                            {{ $t('main.home.backend.connecting') }}
                        </template>
                    </div>
                    <div v-else id="main-menu" class="create-menu mt-5 pt-5">
                        <Options v-if="menuMode == 0" @create="menuMode = 1" @import="importProject" />
                        <Create v-if="menuMode == 1" @cancel="menuMode = 0" @create="createProject" />
                    </div>
                    <template v-if="panoptic.isConnected">
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
                    </template>
                    <!-- remplace la liste des plugins hors connexion: le logo garde sa place -->
                    <div v-else class="flex-grow-1"></div>
                </div>
                <div v-if="panoptic.isConnected" class="user-section">
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

.project-empty {
    padding: 10px;
    font-size: 13px;
}

.old-project .project {
    cursor: default;
    color: rgb(150, 150, 150);
}

.old-project .project:hover {
    background-color: transparent;
}

.legacy-section {
    margin: 15px 15px 0 10px;
    padding-top: 10px;
    border-top: 1px solid var(--border-color);
    font-size: 13px;
    color: rgb(90, 90, 90);
}

.legacy-project {
    padding: 10px;
    margin-right: 15px;
    color: rgb(150, 150, 150);
}

/* Bouton, progression et échec partagent cette hauteur: la ligne ne bouge pas */
.convert-slot {
    height: 30px;
    margin-top: 4px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: flex-start;
}

.convert-btn {
    background-color: rgb(170, 170, 255);
    color: white;
    border-radius: 8px;
    padding: 2px 8px;
    cursor: pointer;
    white-space: nowrap;
}

/* une seule migration 0.x à la fois côté backend */
.convert-btn.disabled {
    background-color: rgb(220, 220, 220);
    color: rgb(150, 150, 150);
    cursor: default;
}

.convert-label {
    display: flex;
    gap: 6px;
    width: 100%;
    font-size: 12px;
    line-height: 16px;
    color: rgb(90, 90, 90);
}

.convert-label .text-truncate {
    flex-grow: 1;
}

.convert-label.failed {
    color: rgb(160, 40, 30);
}

.convert-bar {
    width: 100%;
    height: 4px;
    margin-top: 4px;
    border-radius: 2px;
    background-color: rgb(225, 225, 235);
    overflow: hidden;
}

.convert-bar > div {
    height: 100%;
    background-color: rgb(170, 170, 255);
    transition: width 0.3s ease;
}

/* conversion sur place: pas d'étapes remontées, barre animée */
.convert-bar.indeterminate > div {
    width: 30%;
    animation: convert-slide 1.2s ease-in-out infinite;
}

@keyframes convert-slide {
    from { transform: translateX(-100%); }
    to { transform: translateX(340%); }
}
</style>
