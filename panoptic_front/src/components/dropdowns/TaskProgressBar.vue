<script setup lang="ts">
import { computed } from 'vue'
import { useProjectStore } from '@/data/projectStore'
import Dropdown from '@/components/dropdowns/Dropdown.vue'
import type { TaskState } from '@/data/models'

const project = useProjectStore()

const tasks = computed<TaskState[]>(() => project.state?.tasks ?? [])
const running = computed(() => tasks.value.filter(t => t.running))
const finished = computed(() => tasks.value.filter(t => t.finished && !t.running))

const activePrimary = computed(() => running.value[0] ?? null)
const remainingCount = computed(() => running.value.length - 1)

const primaryPct = computed(() => {
    const t = activePrimary.value
    if (!t || !t.total) return 0
    return Math.min(100, Math.round((t.done / t.total) * 100))
})

const showAny = computed(() => running.value.length > 0 || finished.value.length > 0)

function taskPct(t: TaskState) {
    if (!t.total) return 0
    return Math.min(100, Math.round((t.done / t.total) * 100))
}
</script>

<template>
    <Dropdown v-if="showAny" placement="bottom" :offset="6">
        <template #button>
            <div class="task-progress-btn" :title="activePrimary?.name">
                <i class="bi bi-cpu me-1" style="color: black;" />
                <span v-if="activePrimary" class="task-progress-name">{{ activePrimary.name }}</span>
                <span v-else class="task-progress-name">Tasks</span>
                <span v-if="remainingCount > 0" class="task-progress-queue">+{{ remainingCount }}</span>
                <div class="task-progress-track">
                    <div class="task-progress-fill" :style="{ width: primaryPct + '%' }" />
                </div>
                <span v-if="activePrimary" class="task-progress-pct">{{ primaryPct }}%</span>
            </div>
        </template>
        <template #popup>
            <div class="task-dropdown">
                <div v-if="running.length > 0" class="task-section-label">Running</div>
                <div v-for="t in running" :key="t.id" class="task-row">
                    <div class="task-row-header">
                        <span class="task-row-name">{{ t.name }}</span>
                        <span class="task-row-counts">{{ t.done }}/{{ t.total }}</span>
                        <span v-if="t.failed > 0" class="task-row-failed">{{ t.failed }} failed</span>
                    </div>
                    <div class="task-row-track">
                        <div class="task-row-fill" :style="{ width: taskPct(t) + '%' }" />
                        <div v-if="t.failed > 0" class="task-row-fill task-row-fill--danger"
                            :style="{ width: (t.total ? t.failed / t.total * 100 : 0) + '%' }" />
                    </div>
                </div>

                <div v-if="finished.length > 0" class="task-section-label" :class="{ 'task-section-label--past': running.length > 0 }">Past</div>
                <div v-for="t in finished" :key="t.id" class="task-row task-row--done">
                    <div class="task-row-header">
                        <i class="bi bi-check-circle-fill task-done-icon" />
                        <span class="task-row-name">{{ t.name }}</span>
                        <span class="task-row-counts">{{ t.done }}/{{ t.total }}</span>
                        <span v-if="t.failed > 0" class="task-row-failed">{{ t.failed }} failed</span>
                    </div>
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
