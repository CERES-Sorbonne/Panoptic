<script setup lang="ts">
// Top toolbar root node — inserted into AppShellLayout's #toolbar slot.
//   Left:   project title + project actions (close / settings), like Menu.vue
//   Center: data / column load status (ColumnStatusDropdown, incl. live load progress)
//   Right:  current user + notifications + language, like TabNav.vue
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ModalId } from '@/data/models'
import { useProjectStore } from '@/data/projectStore'
import { usePanopticStore } from '@/data/panopticStore'
import wTT from '@/components/tooltips/withToolTip.vue'
import ColumnStatusDropdown from '../dropdowns/ColumnStatusDropdown.vue'
import TaskProgressBar from '@/components/dropdowns/TaskProgressBar.vue'
import Dropdown from '@/components/dropdowns/Dropdown.vue'
import { useTabStore } from '@/data/tabStore'
import { useColumnStore } from '@/data/columnStore'
import SelectionStamp from '../selection/SelectionStamp.vue'
import TabPanel from './TabPanel.vue'

const { locale } = useI18n()
const project = useProjectStore()
const panoptic = usePanopticStore()
const tab = useTabStore()
const col = useColumnStore()

const langs = ['fr', 'en']

const projectName = computed(() => project.state?.name ?? '')
const currentUser = computed(() => panoptic.connectionState?.user?.name ?? null)

// Global selection ids, reactive via selectionVersion.
const selectedImageIds = computed(() => { col.selectionVersion.value; return col.getSelectedIds() })
const hasSelectedImages = computed(() => selectedImageIds.value.length)

function clearSelection() {
    tab.activeManager?.collection.groupManager.clearSelection()
}

function onChangeLang(event: Event) {
    const lang = (event.target as HTMLSelectElement).value
    locale.value = lang
    project.setLang(lang)
}

function closeProject() {
    panoptic.closeProject(project.state.id)
}
</script>

<template>
    <div class="toolbar">
        <!-- Left: project dropdown + settings -->
        <div class="bar-group">
            <Dropdown placement="bottom-start" :offset="0">
                <template #button>
                    <div class="project-trigger" :title="projectName">
                        <span class="project-name">{{ projectName }}</span>
                    </div>
                </template>
                <template #popup="{ hide }">
                    <div class="project-menu">
                        <div class="menu-item" @click="() => { panoptic.showModal(ModalId.SETTINGS); hide(); }">
                            <i class="bi bi-gear"></i>
                            <span>Settings</span>
                        </div>
                        <div class="menu-item" @click="() => { closeProject(); hide(); }">
                            <i class="bi bi-box-arrow-left"></i>
                            <span>Close project</span>
                        </div>
                    </div>
                </template>
            </Dropdown>
        </div>

        <!-- Center: data / column load status + task progress -->
        <div class="center-tools">
            <ColumnStatusDropdown v-if="tab.activeManager" :tab="tab.activeManager" />
            <TaskProgressBar />
        </div>

        <!-- Right: current user + notifications + language -->
        <div class="bar-group" style="margin-left: auto;">

            <SelectionStamp v-if="hasSelectedImages" style="font-size: 14px;"
                :selected-images-ids="selectedImageIds" @remove:selected="clearSelection"
                @stamped="clearSelection" />
            <TabPanel />
            <span v-if="currentUser" class="user-name" :title="currentUser">
                <i class="bi bi-person-circle"></i>
                <span class="user-name-label">{{ currentUser }}</span>
            </span>
            <wTT message="modals.notif.icon">
                <button class="icon-btn" @click="panoptic.showModal(ModalId.NOTIF)">
                    <i class="bi bi-bell"></i>
                </button>
            </wTT>
            <div class="lang">
                <i class="bi bi-translate"></i>
                <select :value="locale" @change="onChangeLang">
                    <option v-for="(lang, i) in langs" :key="`Lang${i}`" :value="lang">
                        {{ lang.toUpperCase() }}
                    </option>
                </select>
            </div>
        </div>
    </div>
</template>

<style scoped>
.toolbar {
    --bar-tool-height: 28px;
    margin-top: 6px;
    display: flex;
    align-items: center;
    justify-content: flex-start;
    flex: 1;
    gap: var(--spacing-sm);
    padding: 0 var(--spacing-xs);
    overflow: hidden;
}

.bar-group {
    display: flex;
    align-items: center;
    gap: var(--spacing-xs);
    min-width: 0;
}

.bar-group.center {
    flex: 1;
    justify-content: center;
    overflow: hidden;
}

.project-trigger {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    height: var(--bar-tool-height);
    box-sizing: border-box;
    padding: 0 8px;
    /* background-color: var(--primary); */
    border: 1px solid var(--border-color, #dee2e6);
    cursor: pointer;
    /* color: var(--text-inverse); */
    font-size: 0.8rem;
    min-width: 90px;
    justify-content: flex-start;
    border-radius: var(--radius-sm);
}

/* Keep the column-status and task-progress triggers the same height as the
   project dropdown (their internal buttons live in child components). */
.center-tools {
    display: flex;
    align-items: center;
    gap: 6px;
}

.center-tools :deep(.col-status-btn),
.center-tools :deep(.task-progress-btn) {
    height: var(--bar-tool-height);
    box-sizing: border-box;
}

.project-trigger:hover {
    background-color: #b8d4ed;
}

.project-name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    text-align: left;
    width: 100%;
}

.project-menu {
    padding: 3px;
}

.menu-item {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 4px 10px 4px 8px;
    border-radius: var(--radius-sm);
    cursor: pointer;
    white-space: nowrap;
    color: var(--text-secondary);
    font-size: var(--font-size-sm);
    border: none;
    background: none;
    width: 100%;
    justify-content: flex-start;
}

.menu-item:hover {
    background-color: var(--hover-bg);
    color: var(--text-primary);
}

.chip-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    flex-shrink: 0;
    border-radius: var(--radius-sm);
    background-color: var(--primary);
    color: var(--text-inverse);
    font-size: 10px;
    font-weight: var(--font-weight-bold);
}

.icon-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    background: none;
    border: none;
    border-radius: var(--radius-md);
    color: var(--text-primary);
    font-size: 14px;
    transition: background-color var(--transition-fast);
}

.icon-btn:hover {
    background-color: var(--hover-bg);
}

.user-name {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    max-width: 160px;
    color: var(--text-secondary);
    font-size: var(--font-size-sm);
}

.user-name-label {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.lang {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    color: var(--text-secondary);
    font-size: var(--font-size-sm);
}

.lang select {
    background: none;
    border: none;
    color: var(--text-primary);
    font-size: var(--font-size-sm);
    cursor: pointer;
}
</style>
