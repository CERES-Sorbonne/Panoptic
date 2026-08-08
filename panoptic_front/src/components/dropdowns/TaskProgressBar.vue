<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useProjectStore } from '@/data/projectStore'
import Dropdown from '@/components/dropdowns/Dropdown.vue'
import type { TaskState } from '@/data/models'

const project = useProjectStore()
const { t: $t, te } = useI18n()

const tasks = computed<TaskState[]>(() => project.state?.tasks ?? [])
const running = computed(() => tasks.value.filter(t => t.running))
const pending = computed(() => tasks.value.filter(t => !t.running && !t.finished))
const finished = computed(() => tasks.value.filter(t => t.finished && !t.running))

const activePrimary = computed(() => running.value[0] ?? null)
const remainingCount = computed(() => tasks.value.filter(t => !t.finished).length - (activePrimary.value ? 1 : 0))

const primaryPct = computed(() => {
    const t = activePrimary.value
    if (!t || !t.total) return 0
    return Math.min(100, Math.round((t.done / t.total) * 100))
})

const showAny = computed(() => tasks.value.length > 0)

function taskPct(t: TaskState) {
    if (!t.total) return 0
    return Math.min(100, Math.round((t.done / t.total) * 100))
}

// The backend sends raw class names / English steps: map the known ones to
// user friendly labels, and fall back to the raw value for anything unknown
// (plugin tasks we don't ship translations for).
function taskLabel(t: TaskState) {
    const key = `dropdown.tasks.names.${t.key}`
    return te(key) ? $t(key) : t.name
}

function stepLabel(step: string) {
    const key = `dropdown.tasks.steps.${step}`
    return te(key) ? $t(key) : step
}

// The free-form progress message the backend reports (step + detail).
function taskMessage(t: TaskState) {
    if (!t.step) return ''
    const step = stepLabel(t.step)
    return t.detail ? `${step}: ${t.detail}` : step
}

function taskSubtitle(t: TaskState) {
    const parts: string[] = []
    const message = taskMessage(t)
    if (message) parts.push(message)
    if (t.workers) parts.push($t('dropdown.tasks.workers', { count: t.workers }))
    if (t.rate) parts.push($t('dropdown.tasks.rate', { rate: t.rate.toFixed(1) }))
    if (t.eta_seconds) parts.push($t('dropdown.tasks.eta', { time: formatEta(t.eta_seconds) }))
    return parts.join(' · ')
}

function formatEta(seconds: number) {
    if (seconds < 60) return $t('dropdown.tasks.seconds', { value: Math.round(seconds) })
    const minutes = Math.round(seconds / 60)
    if (minutes < 60) return $t('dropdown.tasks.minutes', { value: minutes })
    return $t('dropdown.tasks.hours', { value: Math.round(minutes / 60) })
}
</script>

<template>
    <Dropdown v-if="showAny" placement="bottom" :offset="6">
        <template #button>
            <div class="task-progress-btn" :title="activePrimary ? taskSubtitle(activePrimary) || taskLabel(activePrimary) : ''">
                <i class="bi bi-cpu me-1" style="color: black;" />
                <span v-if="activePrimary" class="task-progress-name">{{ taskLabel(activePrimary) }}</span>
                <span v-else class="task-progress-name">{{ $t('dropdown.tasks.title') }}</span>
                <span v-if="remainingCount > 0" class="task-progress-queue">+{{ remainingCount }}</span>
                <div class="task-progress-track">
                    <div class="task-progress-fill" :style="{ width: primaryPct + '%' }" />
                </div>
                <span v-if="activePrimary" class="task-progress-pct">{{ primaryPct }}%</span>
            </div>
        </template>
        <template #popup>
            <div class="task-dropdown">
                <div v-if="running.length > 0" class="task-section-label">{{ $t('dropdown.tasks.running') }}</div>
                <div v-for="t in running" :key="t.id" class="task-row">
                    <div class="task-row-header">
                        <span class="task-row-name">{{ taskLabel(t) }}</span>
                        <span class="task-row-counts">{{ t.done }}/{{ t.total }}</span>
                        <span v-if="t.failed > 0" class="task-row-failed">{{ $t('dropdown.tasks.failed', { count: t.failed }) }}</span>
                    </div>
                    <div v-if="taskSubtitle(t)" class="task-row-subtitle">{{ taskSubtitle(t) }}</div>
                    <div class="task-row-track">
                        <div class="task-row-fill" :style="{ width: taskPct(t) + '%' }" />
                        <div v-if="t.failed > 0" class="task-row-fill task-row-fill--danger"
                            :style="{ width: (t.total ? t.failed / t.total * 100 : 0) + '%' }" />
                    </div>
                </div>

                <div v-if="pending.length > 0" class="task-section-label"
                    :class="{ 'task-section-label--past': running.length > 0 }">{{ $t('dropdown.tasks.pending') }}</div>
                <div v-for="t in pending" :key="t.id" class="task-row task-row--pending">
                    <div class="task-row-header">
                        <i class="bi bi-hourglass task-pending-icon" />
                        <span class="task-row-name">{{ taskLabel(t) }}</span>
                        <span v-if="t.total" class="task-row-counts">{{ t.done }}/{{ t.total }}</span>
                        <span v-if="t.failed > 0" class="task-row-failed">{{ $t('dropdown.tasks.failed', { count: t.failed }) }}</span>
                    </div>
                    <div class="task-row-subtitle">{{ taskSubtitle(t) || $t('dropdown.tasks.waiting') }}</div>
                </div>

                <div v-if="finished.length > 0" class="task-section-label"
                    :class="{ 'task-section-label--past': running.length > 0 || pending.length > 0 }">{{ $t('dropdown.tasks.past') }}</div>
                <div v-for="t in finished" :key="t.id" class="task-row task-row--done">
                    <div class="task-row-header">
                        <i class="bi bi-check-circle-fill task-done-icon" />
                        <span class="task-row-name">{{ taskLabel(t) }}</span>
                        <span class="task-row-counts">{{ t.done }}/{{ t.total }}</span>
                        <span v-if="t.failed > 0" class="task-row-failed">{{ $t('dropdown.tasks.failed', { count: t.failed }) }}</span>
                    </div>
                    <div class="task-row-subtitle">{{ taskMessage(t) || $t('dropdown.tasks.done') }}</div>
                </div>
            </div>
        </template>
    </Dropdown>
</template>

<style scoped>
.task-progress-btn {
    display: flex;
    align-items: center;
    gap: 5px;
    padding: 4px 8px;
    border: 1px solid var(--border-color, #dee2e6);
    border-radius: 5px;
    font-size: 12px;
    color: var(--text-color, #444);
    white-space: nowrap;
    cursor: pointer;
    background: none;
}

.task-progress-btn:hover {
    background-color: var(--hover-bg);
}

.task-progress-name {
    font-size: 11px;
    color: #666;
    max-width: 120px;
    overflow: hidden;
    text-overflow: ellipsis;
}

.task-progress-queue {
    font-size: 10px;
    color: #aaa;
}

.task-progress-track {
    position: relative;
    width: 60px;
    height: 5px;
    background: #e9ecef;
    border-radius: 3px;
    overflow: hidden;
}

.task-progress-fill {
    position: absolute;
    top: 0;
    left: 0;
    height: 100%;
    width: 0;
    background: #4dabf7;
    transition: width 0.2s linear;
}

.task-progress-pct {
    font-size: 10px;
    color: #888;
    min-width: 28px;
    text-align: right;
}

/* Dropdown panel */
.task-dropdown {
    padding: 6px;
    min-width: 220px;
    max-width: 300px;
}

.task-section-label {
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    color: #aaa;
    padding: 4px 4px 2px;
    letter-spacing: 0.05em;
}

.task-section-label--past {
    margin-top: 6px;
    border-top: 1px solid var(--border-color, #dee2e6);
    padding-top: 8px;
}

.task-row {
    padding: 4px 4px;
    border-radius: 4px;
}

.task-row--done {
    opacity: 0.6;
}

.task-row--pending {
    opacity: 0.75;
}

.task-pending-icon {
    color: #888;
    font-size: 11px;
    flex-shrink: 0;
}

.task-row-header {
    display: flex;
    align-items: center;
    gap: 5px;
    margin-bottom: 3px;
}

.task-row-name {
    font-size: 12px;
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.task-row-counts {
    font-size: 11px;
    color: #888;
    white-space: nowrap;
}

.task-row-subtitle {
    font-size: 10px;
    color: #999;
    margin: -2px 0 3px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.task-row-failed {
    font-size: 11px;
    color: #e03131;
    white-space: nowrap;
}

.task-done-icon {
    color: black;
    font-size: 11px;
    flex-shrink: 0;
}

.task-row-track {
    position: relative;
    width: 100%;
    height: 4px;
    background: #e9ecef;
    border-radius: 3px;
    overflow: hidden;
    display: flex;
}

.task-row-fill {
    height: 100%;
    background: #4dabf7;
    transition: width 0.2s linear;
}

.task-row-fill--danger {
    background: #e03131;
}
</style>
