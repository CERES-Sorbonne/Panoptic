/**
 * TabStore
 * Keeps all data related to open tabs.
 *
 * Design (see notes/tabstore_manager_reactivity_refactor.md):
 *  - Pillar A: every TabState is made reactive at import and the SAME proxy is
 *    handed to both `tabs[id]` and its `TabManager`, so
 *    `manager.state === tabs[id]` (single source of truth, no raw/proxy split).
 *  - Pillar C: persistence is a single debounced deep watch on the ACTIVE tab,
 *    re-armed on tab switch and flushed when switching away.
 *  - Pillar E: `managers` is closure-scoped (not a module global); `deleteTab`
 *    also removes `tabs[id]`; a version mismatch warns + resets instead of
 *    silently dropping.
 */

import { defineStore } from "pinia";
import { computed, reactive, ref, watch, WatchStopHandle } from "vue";
import { TabState } from "./models";
import { TabManager } from "@/core/TabManager";
import { buildTabState, objValues } from "./builder";
import { useProjectStore } from "./projectStore";
import { apiGetAllTabs, apiCreateTab, apiUpdateTabState, apiDeleteTab, apiGetUIData, apiSetUIData } from "./apiProjectRoutes";
import { deepCopy } from "@/utils/utils";

export const TAB_MODEL_VERSION = 9
const TAB_ORDER_KEY = 'tab_order'
const SAVE_DEBOUNCE_MS = 400

export const useTabStore = defineStore('tabStore', () => {
    const loaded = ref(false)
    const mainTab = ref<string>(null)

    const loadedTabs = ref<string[]>([])
    const tabs = reactive<Record<string, TabState>>({})
    // Managers are closure-scoped, not a module global (Pillar E). Class
    // instances are intentionally NOT reactive; reactivity flows through their
    // `.state`, which is the same proxy as `tabs[id]`.
    const managers: Record<string, TabManager> = {}

    const activeTab = computed(() => mainTab.value ? tabs[mainTab.value] : null)
    const activeManager = computed(() => mainTab.value ? managers[mainTab.value] : null)

    // ── Autosave (Pillar C) ─────────────────────────────────────────────────
    // One debounced deep watch on the active tab, re-armed whenever mainTab
    // changes and flushed when switching away.
    let stopSave: WatchStopHandle | null = null
    let flushSave: () => void = () => {}

    function serialize(state: TabState): TabState {
        // Send plain JSON: strip the reactive proxy. `result`/`runState` live on
        // the managers, never on TabState, so they are not in this object.
        return deepCopy(state)
    }

    function armAutosave(id: string | null) {
        flushSave()
        stopSave?.()
        stopSave = null
        flushSave = () => {}
        if (!id) return

        let timer: ReturnType<typeof setTimeout> | null = null
        const run = () => {
            timer = null
            if (!loaded.value || !tabs[id]) return
            apiUpdateTabState(id, serialize(tabs[id]))
        }
        const debounced = () => {
            if (timer) clearTimeout(timer)
            timer = setTimeout(run, SAVE_DEBOUNCE_MS)
        }
        flushSave = () => { if (timer) { clearTimeout(timer); run() } }

        stopSave = watch(() => tabs[id], () => { if (loaded.value) debounced() }, { deep: true })
    }

    watch(mainTab, (id) => armAutosave(id))

    async function init() {
        await loadTabsFromStorage()
        loaded.value = true
    }

    async function clear() {
        flushSave()
        stopSave?.()
        stopSave = null
        flushSave = () => {}
        loaded.value = false
        mainTab.value = null
        for (const k of Object.keys(managers)) delete managers[k]
        loadedTabs.value = []
        Object.keys(tabs).forEach(k => delete tabs[k])
    }

    function importTab(raw: TabState) {
        const id = raw.id
        if (loadedTabs.value.includes(id)) {
            console.warn('import tab that already exist. why ?')
            return
        }
        // Pillar A: wrap once and share the proxy with the manager.
        const tab = reactive(raw) as TabState
        loadedTabs.value.push(id)
        tabs[id] = tab
        const manager = new TabManager(tab)
        managers[id] = manager
        manager.deactivate()
    }

    function getTab(id: string) {
        return managers[id]
    }

    // Legacy accessor kept for non-component / imperative callers. Returns the
    // active manager (may be undefined before load). Components should prefer the
    // reactive `activeManager` / `useCurrentTab()` (Pillar D).
    function getMainTab() {
        return managers[mainTab.value]
    }

    async function saveTabOrder() {
        await apiSetUIData(TAB_ORDER_KEY, loadedTabs.value)
    }

    async function loadTabsFromStorage() {
        const [apiTabs, savedOrder] = await Promise.all([
            apiGetAllTabs(),
            apiGetUIData(TAB_ORDER_KEY) as Promise<string[] | null>,
        ])

        const validTabs = new Map<string, TabState>()
        for (const tabData of apiTabs) {
            const state = tabData.state
            if (!state) continue
            // Pillar E / Q9: warn + reset (drop) on version mismatch instead of
            // silently discarding. Mismatched tabs are not migrated.
            if (state.version != TAB_MODEL_VERSION) {
                console.warn(`[tabStore] dropping tab ${state.id}: version ${state.version} != ${TAB_MODEL_VERSION} (reset)`)
                continue
            }
            validTabs.set(state.id, state)
        }

        // Restore saved order, keeping only tabs that still exist in the DB.
        // Tabs not present in savedOrder (e.g. created on another client) are
        // appended at the end in their DB-returned order.
        const order: string[] = savedOrder ?? []
        const ordered: TabState[] = []
        for (const id of order) {
            const state = validTabs.get(id)
            if (state) {
                ordered.push(state)
                validTabs.delete(id)
            }
        }
        for (const state of validTabs.values()) {
            ordered.push(state)
        }

        for (const tab of ordered) {
            importTab(tab)
        }

        if (!ordered.length) {
            await addTab()
        }

        const savedActiveTab = useProjectStore().uiState?.activeTab
        if (savedActiveTab && loadedTabs.value.includes(savedActiveTab)) {
            await selectMainTab(savedActiveTab)
        } else {
            await selectMainTab(loadedTabs.value[0])
        }
    }

    async function addTab(name?: string, isSelection?: boolean, selection?: number[]) {
        const tab = buildTabState()
        tab.isSelection = isSelection
        const id = crypto.randomUUID()
        tab.id = id
        if (name) tab.name = name
        importTab(tab)
        managers[id].isNew = true
        await selectMainTab(id)
        await Promise.all([
            apiCreateTab(id, tab, selection),
            saveTabOrder(),
        ])
        return tab
    }

    async function deleteTab(id: string) {
        loadedTabs.value = loadedTabs.value.filter(t => t != id)
        delete managers[id]
        delete tabs[id]
        await Promise.all([
            apiDeleteTab(id),
            saveTabOrder(),
        ])
        if (mainTab.value == id && loadedTabs.value.length) {
            await selectMainTab(loadedTabs.value[0])
        } else if (!loadedTabs.value.length) {
            await addTab()
        }
    }

    async function selectMainTab(id: string) {
        if (!managers[id]) return

        for (const manager of objValues(managers)) {
            manager.deactivate()
        }

        mainTab.value = id
        managers[id].activate()
        await managers[id].update()

        useProjectStore().uiState.activeTab = id
        await useProjectStore().saveUiState()
    }

    return {
        loaded, init, clear, getTab, mainTab, deleteTab, addTab, loadedTabs,
        selectMainTab, getMainTab, tabs, activeTab, activeManager,
    }

})
