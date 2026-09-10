<script setup lang="ts">
/**
 * Propose de convertir les projets détectés d'une ancienne version de Panoptic (0.x).
 * Le projet d'origine n'est jamais modifié: une copie convertie est écrite dans un nouveau dossier.
 */
import { computed, reactive, ref, watch } from 'vue';
import { LegacyProject, ModalId } from '@/data/models';
import { usePanopticStore } from '@/data/panopticStore';
import { useModalStore } from '@/data/modalStore';

const panoptic = usePanopticStore()
const modalStore = useModalStore()

// Les 6 étapes du pipeline, dans l'ordre émis par le backend
const STAGES = ['read-legacy', 'write-data-db', 'write-media-db', 'write-project-db', 'check', 'register-project']

const isActive = computed(() => modalStore.isOpen(ModalId.LEGACY))

// destination éditable par projet, préremplie avec suggestedPath
const destPaths = reactive<{ [legacyPath: string]: string }>({})
const errorMessage = ref('')
const showWarnings = ref(false)

const scan = computed(() => panoptic.legacyScan)
const projects = computed(() => panoptic.legacyProjects)
const run = computed(() => panoptic.legacyMigration)
const isRunning = computed(() => panoptic.isMigrationRunning)
const isDone = computed(() => run.value?.status == 'done')
const isFailed = computed(() => run.value?.status == 'failed')

function canMigrate(project: LegacyProject) {
    return project.exists && !!project.shape && !project.migratedTo
}

function destPath(project: LegacyProject) {
    if (destPaths[project.legacyPath] === undefined) {
        destPaths[project.legacyPath] = project.suggestedPath
    }
    return destPaths[project.legacyPath]
}

function promptPath(project: LegacyProject) {
    panoptic.showModal(ModalId.FOLDERSELECTION, {
        callback: (path: string) => {
            if (!path) return
            destPaths[project.legacyPath] = path
        },
        mode: 'create'
    })
}

function readableSize(bytes?: number) {
    if (!bytes) return ''
    const units = ['o', 'Ko', 'Mo', 'Go']
    let value = bytes
    let unit = 0
    while (value > 1024 && unit < units.length - 1) {
        value /= 1024
        unit += 1
    }
    return value.toFixed(1) + ' ' + units[unit]
}

function stageState(stage: string) {
    const r = run.value
    if (!r) return 'todo'
    const index = STAGES.indexOf(stage)
    const current = r.stage == 'done' ? STAGES.length : STAGES.indexOf(r.stage ?? '')
    if (index < current) return 'done'
    if (index == current) return isFailed.value ? 'failed' : 'current'
    return 'todo'
}

async function migrate(project: LegacyProject) {
    errorMessage.value = ''
    try {
        await panoptic.migrateLegacyProject(project.legacyPath, destPath(project), project.name, false)
    } catch (e: any) {
        // Les refus du backend (destination non vide, migration en cours, ...) sont des messages lisibles
        errorMessage.value = e?.response?.data?.message ?? e?.message ?? ''
    }
}

async function dismiss(project?: LegacyProject) {
    await panoptic.dismissLegacy(project?.legacyPath)
    if (!panoptic.legacyProjects.length) hide()
}

function openReport() {
    if (!run.value) return
    window.open(panoptic.getLegacyReportUrl(run.value.id), '_blank')
}

function hide() {
    panoptic.hideModal(ModalId.LEGACY)
}

// une migration terminée laisse le panneau de résultat ouvert, mais on relit le scan
watch(() => run.value?.status, (status) => {
    if (status == 'done') panoptic.fetchLegacyProjects()
})

modalStore.registerModal(ModalId.LEGACY, 1)
</script>

<template>
    <div v-if="isActive" class="legacy-backdrop" @click.self="hide">
        <div class="legacy-modal">
            <div class="legacy-title d-flex">
                <b class="flex-grow-1">{{ $t('modals.legacy.title') }}</b>
                <div class="bb bi bi-x" @click="hide"></div>
            </div>
            <div class="legacy-body">
                <div class="safety">
                    <i class="bi bi-shield-check me-1"></i>{{ $t('modals.legacy.safety') }}
                </div>

                <div v-if="scan?.registries?.length" class="dimmed mb-2">
                    <div v-for="registry in scan.registries" :key="registry.path">
                        <i class="bi bi-database me-1"></i>
                        {{ $t('modals.legacy.registry', { count: registry.projects, shape: registry.shape }) }}
                        <span class="path">{{ registry.path }}</span>
                        <span v-if="registry.problem" class="warn ms-1">{{ registry.problem }}</span>
                    </div>
                </div>

                <div v-if="errorMessage" class="alert-error mb-2">{{ errorMessage }}</div>

                <table class="legacy-table">
                    <tr v-for="project in projects" :key="project.legacyPath">
                        <td>
                            <div><b>{{ project.name }}</b></div>
                            <div class="path">{{ project.legacyPath }}</div>
                            <div class="dimmed">
                                <span v-if="project.shape">{{ $t('modals.legacy.shape') }}: {{ project.shape }}</span>
                                <span v-if="project.instanceCount != null" class="ms-2">
                                    {{ $t('modals.legacy.images', { count: project.instanceCount }) }}
                                </span>
                                <span v-if="project.dbSize" class="ms-2">{{ readableSize(project.dbSize) }}</span>
                            </div>
                            <div v-if="project.plugins?.length" class="dimmed">
                                {{ $t('modals.legacy.plugins', { plugins: project.plugins.join(', ') }) }}
                            </div>
                            <!-- problem peut n'être qu'un avertissement: on l'affiche sans bloquer -->
                            <div v-if="project.problem" class="warn">{{ project.problem }}</div>
                            <div v-if="project.migratedTo" class="ok">
                                {{ $t('modals.legacy.already') }} <span class="path">{{ project.migratedTo }}</span>
                            </div>
                            <div v-if="project.status == 'failed'" class="warn">{{ $t('modals.legacy.previous_failed') }}
                            </div>
                        </td>
                        <td class="dest">
                            <template v-if="canMigrate(project)">
                                <div class="dimmed">{{ $t('modals.legacy.destination') }}</div>
                                <div class="d-flex">
                                    <input class="flex-grow-1" :value="destPath(project)" :disabled="isRunning"
                                        @input="e => destPaths[project.legacyPath] = (e.target as any).value" />
                                    <div class="bb ms-1 bi bi-folder2-open" @click="promptPath(project)"></div>
                                </div>
                            </template>
                        </td>
                        <td class="actions">
                            <div v-if="canMigrate(project)" class="legacy-btn"
                                :class="{ disabled: isRunning }" @click="!isRunning && migrate(project)">
                                {{ $t('modals.legacy.migrate') }}
                            </div>
                            <div v-else class="dimmed">{{ $t('modals.legacy.unavailable') }}</div>
                            <div class="bb mt-1" @click="dismiss(project)">{{ $t('modals.legacy.ignore') }}</div>
                        </td>
                    </tr>
                </table>

                <!-- Progression: pilotée par le socket, une seule migration à la fois -->
                <div v-if="run" class="progress-panel mt-3">
                    <b>{{ run.name }}</b>
                    <span class="path ms-1">{{ run.destPath }}</span>
                    <div v-for="stage in STAGES" :key="stage" class="stage" :class="stageState(stage)">
                        <i class="bi me-1"
                            :class="stageState(stage) == 'done' ? 'bi-check-circle' : (stageState(stage) == 'failed' ? 'bi-x-circle' : 'bi-circle')"></i>
                        {{ $t('modals.legacy.stages.' + stage) }}
                    </div>
                    <div v-if="run.detail" class="dimmed">{{ run.detail }}</div>
                </div>

                <!-- Résultat -->
                <div v-if="isDone || isFailed" class="result-panel mt-3">
                    <div v-if="isFailed" class="alert-error">
                        <b>{{ $t('modals.legacy.failed') }}</b>
                        <div v-if="run.error">{{ run.error }}</div>
                        <div>{{ $t('modals.legacy.failed_hint') }}</div>
                    </div>
                    <div v-else class="ok"><b>{{ $t('modals.legacy.done') }}</b></div>

                    <div v-if="run.warnings?.length" class="mt-2">
                        <b class="bb" @click="showWarnings = !showWarnings">
                            <i class="bi me-1" :class="showWarnings ? 'bi-caret-down-fill' : 'bi-caret-right-fill'"></i>
                            {{ $t('modals.legacy.warnings') }}
                        </b>
                        <!-- messages issus du backend: en anglais, affichés tels quels -->
                        <template v-if="showWarnings">
                            <div v-for="(warning, i) in run.warnings" :key="i" class="warn">{{ warning }}</div>
                        </template>
                    </div>

                    <div v-if="isDone" class="mt-2">
                        <b>{{ $t('modals.legacy.losses.title') }}</b>
                        <ul class="m-0">
                            <li>{{ $t('modals.legacy.losses.tabs') }}</li>
                            <li>{{ $t('modals.legacy.losses.vectors') }}</li>
                        </ul>
                    </div>

                    <div v-if="run.plugins?.length" class="dimmed mt-2">
                        {{ $t('modals.legacy.plugins', { plugins: run.plugins.join(', ') }) }}
                    </div>

                    <div class="mt-2">
                        <span class="bb" @click="openReport">
                            <i class="bi bi-file-earmark-text me-1"></i>{{ $t('modals.legacy.report') }}
                        </span>
                    </div>
                </div>

                <hr class="my-3" />

                <div class="d-flex">
                    <div class="flex-grow-1 bb" @click="dismiss()">{{ $t('modals.legacy.dismiss_all') }}</div>
                    <div class="bb" @click="hide">{{ $t('modals.legacy.later') }}</div>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.legacy-backdrop {
    position: fixed;
    inset: 0;
    background-color: rgba(0, 0, 0, 0.4);
    z-index: 1050;
    display: flex;
    align-items: center;
    justify-content: center;
}

.legacy-modal {
    background-color: white;
    border: 2px solid var(--border-color);
    border-radius: 3px;
    width: 900px;
    max-width: 95vw;
    max-height: 90vh;
    display: flex;
    flex-direction: column;
    text-align: left;
    color: rgb(45, 45, 45);
}

.legacy-title {
    background-color: rgb(238, 238, 255);
    padding: 4px 8px;
}

.legacy-body {
    padding: 12px;
    overflow-y: auto;
}

.safety {
    background-color: rgb(232, 245, 233);
    border-radius: 4px;
    padding: 8px;
    margin-bottom: 12px;
}

.legacy-table {
    width: 100%;
}

.legacy-table td {
    border-top: 1px solid var(--border-color);
    padding: 8px 4px;
    vertical-align: top;
}

.dest {
    width: 300px;
}

.actions {
    width: 130px;
    text-align: center;
}

.path {
    font-size: 12px;
    color: rgb(120, 120, 120);
    word-break: break-all;
}

.dimmed {
    font-size: 13px;
    color: rgb(110, 110, 110);
}

.warn {
    font-size: 13px;
    color: rgb(180, 110, 0);
}

.ok {
    font-size: 13px;
    color: rgb(30, 130, 60);
}

.alert-error {
    background-color: rgb(253, 236, 234);
    color: rgb(160, 40, 30);
    border-radius: 4px;
    padding: 8px;
}

.legacy-btn {
    background-color: rgb(170, 170, 255);
    color: white;
    border-radius: 8px;
    padding: 4px;
    cursor: pointer;
}

.legacy-btn.disabled {
    background-color: rgb(220, 220, 220);
    color: rgb(150, 150, 150);
    cursor: default;
}

.progress-panel,
.result-panel {
    border-top: 1px solid var(--border-color);
    padding-top: 8px;
}

.stage {
    font-size: 13px;
    color: rgb(150, 150, 150);
}

.stage.done {
    color: rgb(30, 130, 60);
}

.stage.current {
    color: rgb(60, 60, 200);
    font-weight: bold;
}

.stage.failed {
    color: rgb(160, 40, 30);
}
</style>
