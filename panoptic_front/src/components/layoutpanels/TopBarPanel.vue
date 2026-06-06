<script setup lang="ts">
// Top toolbar root node — inserted into AppShellLayout's #toolbar slot.
//   Left:   project title + project actions (close / settings), like Menu.vue
//   Center: data / column load status (real ColumnLoadProgress)
//   Right:  current user + notifications + language, like TabNav.vue
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ModalId } from '@/data/models'
import { useProjectStore } from '@/data/projectStore'
import { usePanopticStore } from '@/data/panopticStore'
import wTT from '@/components/tooltips/withToolTip.vue'
import ColumnLoadProgress from '@/components/dropdowns/ColumnLoadProgress.vue'
import ColumnStatusDropdown from '../dropdowns/ColumnStatusDropdown.vue'
import { useTabStore } from '@/data/tabStore'

const { locale } = useI18n()
const project = useProjectStore()
const panoptic = usePanopticStore()
const tab = useTabStore()

const langs = ['fr', 'en']

const projectName = computed(() => project.state?.name ?? '')
const projectBadge = computed(() => projectName.value.slice(0, 2).toUpperCase() || '··')
const currentUser = computed(() => panoptic.connectionState?.user?.name ?? null)

function onChangeLang(event: Event) {
    const lang = (event.target as HTMLSelectElement).value
    locale.value = lang
    project.setLang(lang)
}
</script>

<template>
    <div class="toolbar">
        <!-- Left: project title + actions -->
        <div class="bar-group">
            <wTT message="main.menu.close_project">
                <button class="icon-btn close-project" @click="panoptic.closeProject(project.state.id)">
                    <i class="bi bi-arrow-up-left-square"></i>
                </button>
            </wTT>
            <div class="project-badge-name">
                <span class="text-capitalize">{{ projectName }}</span>
            </div>
            <wTT message="Settings">
                <button class="icon-btn" @click="panoptic.showModal(ModalId.SETTINGS)">
                    <i class="bi bi-gear"></i>
                </button>
            </wTT>
        </div>

        <!-- Center: data / column load status -->
        <div  class="d-flex">
            <!-- <ColumnStatusDropdown :tab="tab.getMainTab()" /> -->
            <ColumnLoadProgress />
        </div>

        <!-- Right: current user + notifications + language -->
        <div class="bar-group">
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
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex: 1;
    gap: var(--spacing-sm);
    padding: 0 var(--spacing-sm);
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

.project-badge-name {
    display: inline-flex;
    align-items: center;
    gap: var(--spacing-xs);
    min-width: 60px;
    max-width: 180px;
    padding: 0 var(--spacing-xs);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    background-color: var(--primary);
    color: var(--text-inverse);
}

.project-badge-name .badge {
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

.project-badge-name > span:last-child {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    text-align: left;
    font-weight: var(--font-weight-medium);
    color: var(--text-inverse);
    font-size: var(--font-size-sm);
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

.close-project:hover {
    color: var(--error);
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
