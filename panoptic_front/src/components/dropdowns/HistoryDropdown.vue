<script setup lang="ts">
// History button in the toolbar. The popup lists recent edits (commits) with undo and
// redo arrows. It can show only this user's commits or the commits of all users.
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

// 'own' shows this user's undo and redo stacks from the store. Ctrl+Z works on these.
// 'all' loads the commits of every author from the server. These are only shown:
// the server still runs undo and redo per user.
const scope = ref<'own' | 'all'>('own')
const allHistory = ref<CommitHistory>({ undo: [], redo: [] })
const loading = ref(false)

const history = computed(() => scope.value === 'all' ? allHistory.value : data.history)

// Set a background only while flashing. Any inline background, even `transparent`,
// would win over the :hover rule in the CSS.
const buttonStyle = computed(() => flash.value ? { backgroundColor: '#89b0cd' } : {})

// Show at most maxShow commits on each side. The top of each stack is shown next to the
// arrows: the newest undo is first in its list, and the next redo is last in its list.
const undos = computed(() => [...history.value.undo].reverse().slice(0, maxShow))
const redos = computed(() => history.value.redo.slice(Math.max(history.value.redo.length - maxShow, 0)))

// The arrows always use this user's stacks, even when the list shows all users.
const canUndo = computed(() => data.history.undo.length > 0)
const canRedo = computed(() => data.history.redo.length > 0)

const userNames = computed(() => {
    const res: { [id: string]: string } = {}
    for (const u of panoptic.users) res[u.id] = u.name
    return res
})

// Label for a commit from someone else. Returns the other user's name. If the commit has
// no author (import, plugin, file source, system), returns its source instead.
function authorName(commit: CommitStat) {
    if (commit.own) return undefined
    if (!commit.author) return commit.source
    return userNames.value[commit.author] ?? commit.author
}

async function loadAll() {
    loading.value = true
    try {
        // The user names are needed for the author labels. Some start paths do not load them.
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
    // A stack changed, so reload the list when it shows all users.
    if (scope.value === 'all') loadAll()
})
</script>

<template>
    <Dropdown @show="onShow">
        <template #button>
            <wTT message="dropdown.history.info">
                <div class="history-btn" :style="buttonStyle">
                    <i class="bi bi-clock-history"></i>
                </div>
            </wTT>
        </template>
        <template #popup>
            <div class="history-popup">
                <div class="scope">
                    <div class="scope-btn" :class="{ selected: scope === 'own' }" @click="setScope('own')">
                        {{ $t('dropdown.history.mine') }}
                    </div>
                    <div class="scope-btn" :class="{ selected: scope === 'all' }" @click="setScope('all')">
                        {{ $t('dropdown.history.all') }}
                    </div>
                </div>

                <div v-if="loading" class="placeholder">…</div>
                <template v-else>
                    <div v-if="!history.undo.length && !history.redo.length" class="placeholder">
                        {{ $t('dropdown.history.empty') }}
                    </div>

                    <div v-if="history.redo.length > maxShow" class="more">
                        + {{ history.redo.length - maxShow }}
                    </div>
                    <div v-for="commit in redos" :key="commit.id" class="entry undone">
                        <span class="time">{{ formatTime(commit.timestamp) }}</span>
                        <span v-if="commit.tags">{{ commit.tags }} {{ $t('dropdown.history.tags') }}</span>
                        <span v-if="commit.values">{{ commit.values }} {{ $t('dropdown.history.values') }}</span>
                        <span v-if="authorName(commit)" class="author">{{ authorName(commit) }}</span>
                    </div>

                    <div class="arrows">
                        <wTT v-if="canUndo" message="dropdown.history.undo">
                            <div class="arrow-btn bi bi-arrow-down" @click="data.undo"></div>
                        </wTT>
                        <div v-else class="arrow-btn disabled bi bi-arrow-down"></div>
                        <wTT v-if="canRedo" message="dropdown.history.redo">
                            <div class="arrow-btn bi bi-arrow-up" @click="data.redo"></div>
                        </wTT>
                        <div v-else class="arrow-btn disabled bi bi-arrow-up"></div>
                    </div>

                    <div v-for="commit in undos" :key="commit.id" class="entry">
                        <span class="time">{{ formatTime(commit.timestamp) }}</span>
                        <span v-if="commit.tags">{{ commit.tags }} {{ $t('dropdown.history.tags') }}</span>
                        <span v-if="commit.values">{{ commit.values }} {{ $t('dropdown.history.values') }}</span>
                        <span v-if="authorName(commit)" class="author">{{ authorName(commit) }}</span>
                    </div>
                    <div v-if="history.undo.length > maxShow" class="more">
                        + {{ history.undo.length - maxShow }}
                    </div>
                </template>
            </div>
        </template>
    </Dropdown>
</template>

<style scoped>
.history-popup {
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 220px;
    padding: 8px;
    font-size: 12px;
}

/* Segmented control: two pills inside one rounded track. */
.scope {
    display: flex;
    gap: 2px;
    padding: 2px;
    margin-bottom: 4px;
    border-radius: var(--radius-lg);
    background-color: var(--bg-secondary);
}

.scope-btn {
    flex: 1;
    text-align: center;
    padding: 3px 8px;
    border-radius: var(--radius-md);
    color: var(--text-secondary);
    cursor: pointer;
    transition: background-color var(--transition-fast), color var(--transition-fast);
}

.scope-btn:hover {
    color: var(--text-primary);
}

.scope-btn.selected {
    background-color: var(--bg-primary);
    color: var(--text-primary);
    font-weight: var(--font-weight-medium);
    box-shadow: var(--shadow-sm);
}

.placeholder {
    padding: 6px;
    text-align: center;
    color: var(--text-secondary);
}

.entry {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border-radius: var(--radius-md);
    background-color: var(--bg-secondary);
    white-space: nowrap;
}

.time {
    color: var(--text-secondary);
    font-variant-numeric: tabular-nums;
}

/* Redo entries are commits that are undone right now, so they are crossed out. */
.undone {
    background-color: transparent;
    border: 1px dashed var(--border-light);
    color: var(--text-tertiary);
    text-decoration: line-through;
}

.author {
    margin-left: auto;
    padding: 0 6px;
    border-radius: 999px;
    background-color: var(--primary-light);
    color: var(--primary-dark);
    font-size: 11px;
}

.more {
    align-self: center;
    padding: 1px 8px;
    border-radius: 999px;
    background-color: var(--bg-secondary);
    color: var(--text-secondary);
    font-size: 11px;
}

.arrows {
    display: flex;
    justify-content: center;
    gap: 12px;
    padding: 2px 0;
}

.arrow-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 26px;
    height: 26px;
    border-radius: 50%;
    background-color: var(--primary-light);
    color: var(--primary);
    cursor: pointer;
    transition: background-color var(--transition-fast), color var(--transition-fast);
}

.arrow-btn:hover {
    background-color: var(--primary);
    color: var(--text-inverse);
}

.arrow-btn.disabled {
    background-color: var(--disabled-bg);
    color: var(--disabled-text);
    cursor: default;
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
