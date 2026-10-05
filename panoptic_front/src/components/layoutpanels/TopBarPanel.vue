<script setup lang="ts">
// Top toolbar root node — inserted into AppShellLayout's #toolbar slot.
//   Left:   project title + settings + task progress + history
//   Right:  current user + data load status + notifications + language, like TabNav.vue
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ModalId } from '@/data/models'
import { useProjectStore } from '@/data/stores/projectStore'
import { usePanopticStore } from '@/data/stores/panopticStore'
import wTT from '@/components/tooltips/withToolTip.vue'
import ColumnStatusDropdown from '../dropdowns/ColumnStatusDropdown.vue'
import TaskProgressBar from '@/components/dropdowns/TaskProgressBar.vue'
import HistoryDropdown from '@/components/dropdowns/HistoryDropdown.vue'
import ProfileDropdown from '@/components/dropdowns/ProfileDropdown.vue'
import { useTabStore } from '@/data/stores/tabStore'
import { useColumnStore } from '@/data/stores/columnStore'
import SelectionStamp from '../selection/SelectionStamp.vue'
import TabPanel from './TabPanel.vue'

const { locale } = useI18n()
const project = useProjectStore()
const panoptic = usePanopticStore()
const tab = useTabStore()
const col = useColumnStore()

const langs = ['fr', 'en']

const projectName = computed(() => project.state?.name ?? '')

// Global selection ids, reactive via selectionVersion.
const selectedImageIds = computed(() => { col.selectionVersion; return col.getSelectedIds() })
const hasSelectedImages = computed(() => selectedImageIds.value.length)

function clearSelection() {
    tab.activeManager?.collection.clearSelection()
}

function onChangeLang(event: Event) {
    const lang = (event.target as HTMLSelectElement).value
    locale.value = lang
    project.setLang(lang)
}

</script>

<template>
    <div class="toolbar">
        <!-- Left: project name + settings + task progress + history -->
        <div class="bar-group left-tools">
            <span class="project-name" :title="projectName">{{ projectName }}</span>
            <wTT message="modals.settings.title">
                <button class="icon-btn" @click="panoptic.showModal(ModalId.SETTINGS)">
                    <i class="bi bi-gear"></i>
                </button>
            </wTT>
            <TaskProgressBar />
            <HistoryDropdown />
        </div>

        <!-- Right: current user + data load status + notifications + language -->
        <div class="bar-group" style="margin-left: auto;">

            <SelectionStamp v-if="hasSelectedImages" style="font-size: 14px;"
                :selected-images-ids="selectedImageIds" @remove:selected="clearSelection"
                @stamped="clearSelection" />
            <TabPanel  class="me-1"/>
            <ProfileDropdown />
            <ColumnStatusDropdown v-if="tab.activeManager" :tab="tab.activeManager" />
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
    gap: 0;
    min-width: 0;
}

.bar-group.center {
    flex: 1;
    justify-content: center;
    overflow: hidden;
}

/* Give the history and task-progress triggers (from child components) the
   same box as the .icon-btn buttons. The task button grows past the default
   width while it shows progress. */
.left-tools .icon-btn,
.left-tools :deep(.history-btn),
.left-tools :deep(.task-progress-btn) {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: auto;
    min-width: 24px;
    height: 24px;
    padding: 0;
    box-sizing: border-box;
    border-radius: var(--radius-md);
    color: var(--text-primary);
    font-size: 14px;
}

.left-tools :deep(.task-progress-btn:has(.task-progress-name)) {
    padding: 0 6px;
}

/* Tooltip wrappers are inline spans; make them flex so the icon buttons
   center with the title instead of sitting on the text baseline. */
.bar-group :deep(.wtt-trigger) {
    display: inline-flex;
    align-items: center;
}

/* The Dropdown's trigger wrapper is a plain block, so the trigger sits on a
   text line and drops below center. A flex wrapper removes that line. Only
   the bar's own dropdowns are matched, not the ones inside their popups. */
.bar-group > :deep(div > .v-popper > div) {
    display: flex;
}

/* Center the icons' 1em box. By default Bootstrap Icons shift the glyph down
   to sit on the text baseline. */
.toolbar :deep(:is(.icon-btn, .task-progress-btn, .history-btn, .col-status-btn, .profile-btn, .lang) > .bi) {
    display: inline-flex;
}

.project-name {
    line-height: var(--bar-tool-height);
    max-width: 200px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 0.8rem;
    font-weight: var(--font-weight-bold);
    margin: 0 4px 0 8px;
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

.lang {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    height: 24px;
    padding: 0 4px;
    border-radius: var(--radius-md);
    color: var(--text-primary);
    font-size: 14px;
    cursor: pointer;
    transition: background-color var(--transition-fast);
}

.lang:hover {
    background-color: var(--hover-bg);
}

.lang select {
    appearance: none;
    padding: 0;
    background: none;
    border: none;
    outline: none;
    color: var(--text-primary);
    font-size: var(--font-size-sm);
    cursor: pointer;
}
</style>
