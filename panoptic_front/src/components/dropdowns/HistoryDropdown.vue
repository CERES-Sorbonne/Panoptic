<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import Dropdown from './Dropdown.vue'
import { useDataStore } from '@/data/dataStore'
import { usePanopticStore } from '@/data/panopticStore'
import { apiGetHistory } from '@/data/apiProjectRoutes'
import { CommitHistory, CommitStat } from '@/data/models'
import wTT from '@/components/tooltips/withToolTip.vue'

const data = useDataStore()
const panoptic = usePanopticStore()
const flash = ref(false)

const maxShow = 5

// 'own' reads the store's own-commit stacks (the ones Ctrl+Z acts on). 'all' fetches every
// author's commits: those extra entries are display-only — undo/redo stay per-user server-side.
const scope = ref<'own' | 'all'>('own')
const allHistory = ref<CommitHistory>({ undo: [], redo: [] })
const loading = ref(false)

const history = computed(() => scope.value === 'all' ? allHistory.value : data.history)

// Only set a background while flashing: an inline `transparent` would beat the :hover rule.
const buttonStyle = computed(() => flash.value ? { backgroundColor: '#89b0cd' } : {})

// Newest first on both sides: the undo stack is the last N edits, the redo stack the ones
// closest to being replayed.
const undos = computed(() => [...history.value.undo].reverse().slice(0, maxShow))
const redos = computed(() => history.value.redo.slice(Math.max(history.value.redo.length - maxShow, 0)))

// Arrows always act on this user's own stacks, whatever the dropdown is currently showing.
const canUndo = computed(() => data.history.undo.length > 0)
const canRedo = computed(() => data.history.redo.length > 0)

const userNames = computed(() => {
    const res: { [id: string]: string } = {}
    for (const u of panoptic.users) res[u.id] = u.name
    return res
})

// Label for a commit that isn't this user's: another user's name, or — for commits with no
// author at all (import, plugin, file source, system) — the source that wrote them.
function authorName(commit: CommitStat) {
    if (commit.own) return undefined
    if (!commit.author) return commit.source
    return userNames.value[commit.author] ?? commit.author
}

async function loadAll() {
    loading.value = true
    try {
        // Names for the author column — the user list isn't fetched on every startup path.
        if (!panoptic.users.length) await panoptic.fetchUsers()
        allHistory.value = await apiGetHistory('all')
    } finally {
        loading.value = false
    }
}

function setScope(value: 'own' | 'all') {
    scope.value = value
    if (value === 'all') loadAll()
}

function onShow() {
    if (scope.value === 'all') loadAll()
}

function formatTime(ts: string) {
    return new Date(ts).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
}

watch(() => data.onUndo, () => {
    flash.value = true
    setTimeout(() => flash.value = false, 100)
    // Somebody's stacks moved — keep the project-wide view in sync too.
    if (scope.value === 'all') loadAll()
})
</script>

<template>
    <Dropdown @show="onShow">
        <template #button>
            <wTT message="dropdown.history.info">
                <div class="history-btn" :style="buttonStyle">
                    <i class="bi bi-clock-history flash"></i>
                </div>
            </wTT>
        </template>
        <template #popup>
            <div class="p-2" style="min-width: 210px;">
                <div class="d-flex mb-2 scope">
                    <div class="scope-btn" :class="{ selected: scope === 'own' }" @click="setScope('own')">
                        {{ $t('dropdown.history.mine') }}
                    </div>
                    <div class="scope-btn" :class="{ selected: scope === 'all' }" @click="setScope('all')">
                        {{ $t('dropdown.history.all') }}
                    </div>
                </div>

                <div v-if="loading" class="text-secondary text-center p-1">…</div>
                <template v-else>
                    <div v-if="!history.undo.length && !history.redo.length"
                        class="text-secondary text-center p-1" style="font-size: 12px;">
                        {{ $t('dropdown.history.empty') }}
                    </div>

                    <div v-if="history.redo.length > maxShow" class="entry text-center text-secondary">
                        + {{ history.redo.length - maxShow }}
                    </div>
                    <div v-for="commit in redos" :key="commit.id" class="entry undone">
                        <span>{{ formatTime(commit.timestamp) }}</span>
                        <span class="sep ms-1 me-1"></span>
                        <span v-if="commit.tags">{{ commit.tags }} {{ $t('dropdown.history.tags') }}</span>
                        <span v-if="commit.values">{{ commit.values }} {{ $t('dropdown.history.values') }}</span>
                        <span v-if="authorName(commit)" class="author ms-1">{{ authorName(commit) }}</span>
                    </div>

                    <div class="entry" style="background-color: #f7f7f7;">
                        <div class="d-flex center justify-content-center">
                            <wTT v-if="canUndo" message="dropdown.history.undo">
                                <div class="bi bi-arrow-down sb" @click="data.undo"></div>
                            </wTT>
                            <div v-else class="bi bi-arrow-down text-secondary"></div>
                            <div style="width: 30px;"></div>
                            <wTT v-if="canRedo" message="dropdown.history.redo">
                                <div class="bi bi-arrow-up sb" @click="data.redo"></div>
                            </wTT>
                            <div v-else class="bi bi-arrow-up text-secondary"></div>
                        </div>
                    </div>

                    <div v-for="commit in undos" :key="commit.id" class="entry">
                        <span>{{ formatTime(commit.timestamp) }}</span>
                        <span class="sep ms-1 me-1"></span>
                        <span v-if="commit.tags">{{ commit.tags }} {{ $t('dropdown.history.tags') }}</span>
                        <span v-if="commit.values">{{ commit.values }} {{ $t('dropdown.history.values') }}</span>
                        <span v-if="authorName(commit)" class="author ms-1">{{ authorName(commit) }}</span>
                    </div>
                    <div v-if="history.undo.length > maxShow" class="entry text-center text-secondary">
                        + {{ history.undo.length - maxShow }}
                    </div>
                </template>
            </div>
        </template>
    </Dropdown>
</template>

<style scoped>
.flash {
    transition: background-color 0.5s ease;
}

.entry {
    border: 1px solid var(--border-color);
    padding: 4px;
    margin-bottom: 4px;
    font-size: 12px;
    white-space: nowrap;
}

/* Redo entries are commits currently switched off — show them as struck out. */
.undone {
    color: var(--text-secondary, #6c757d);
    text-decoration: line-through;
}

.author {
    font-size: 11px;
    color: var(--text-secondary, #6c757d);
    font-style: italic;
}

.scope {
    font-size: 12px;
}

.scope-btn {
    flex: 1;
    text-align: center;
    padding: 2px 6px;
    cursor: pointer;
    border: 1px solid var(--border-color);
}

.scope-btn.selected {
    background-color: rgba(137, 176, 205, 0.4);
}

.history-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    box-sizing: border-box;
    border: 1px solid var(--border-color, #dee2e6);
    border-radius: var(--radius-sm);
    color: var(--text-primary);
    cursor: pointer;
    font-size: 14px;
    transition: background-color var(--transition-fast);
}

.history-btn:hover {
    background-color: var(--hover-bg);
}
</style>
