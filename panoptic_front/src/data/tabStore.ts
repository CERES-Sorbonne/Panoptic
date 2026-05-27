/**
 * TabStore
 * Keeps all data related to open tabs
 */

import { defineStore } from "pinia";
import { ref } from "vue";
import { TabData, TabState } from "./models";
import { TabManager } from "@/core/TabManager";
import { buildTabState, objValues } from "./builder";
import { useProjectStore } from "./projectStore";
import { apiGetAllTabs, apiCreateTab, apiUpdateTabState, apiDeleteTab, apiGetUIData, apiSetUIData } from "./apiProjectRoutes";

export const TAB_MODEL_VERSION = 7
const TAB_ORDER_KEY = 'tab_order'

let managers: { [tabId: string]: TabManager } = {}

export const useTabStore = defineStore('tabStore', () => {
    const loaded = ref(false)
    const mainTab = ref<string>(null)

    const loadedTabs = ref<string[]>([])

    async function init() {
        await loadTabsFromStorage()
        loaded.value = true
    }

    async function clear() {
        loaded.value = false
        mainTab.value = null
        managers = {}
        loadedTabs.value = []
    }

    function importTab(tab: TabState) {
        const id = tab.id
        if (loadedTabs.value.includes(id)) {
            console.warn('import tab that already exist. why ?')
            return
        }
        loadedTabs.value.push(id)
        const manager = new TabManager(tab)
        managers[id] = manager
        manager.deactivate()
    }

    function getTab(id: string) {
        return managers[id]
    }

    function getMainTab() {
        return managers[mainTab.value]
    }

    async function saveTabOrder() {
        await apiSetUIData(TAB_ORDER_KEY, loadedTabs.value)
    }

    async function loadTabsFromStorage() {
        const [tabs, savedOrder] = await Promise.all([
            apiGetAllTabs(),
            apiGetUIData(TAB_ORDER_KEY) as Promise<string[] | null>,
        ])

        const validTabs = new Map<string, TabState>()
        for (const tabData of tabs) {
            const state = tabData.state
            if (!state || state.version != TAB_MODEL_VERSION) continue
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

        const activeTab = useProjectStore().uiState?.activeTab
        if (activeTab && loadedTabs.value.includes(activeTab)) {
            await selectMainTab(activeTab)
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
        await Promise.all([
            apiCreateTab(id, tab, selection),
            saveTabOrder(),
        ])
        mainTab.value = id
        managers[id].isNew = true
        await selectMainTab(id)
        return tab
    }

    async function deleteTab(id: string) {
        loadedTabs.value = loadedTabs.value.filter(t => t != id)
        delete managers[id]
        await Promise.all([
            apiDeleteTab(id),
            saveTabOrder(),
        ])
        if (mainTab.value == id && loadedTabs.value.length) {
            await selectMainTab(loadedTabs.value[0])
        } else if (!loadedTabs.value.length) {
            addTab()
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

    async function updateTabStateInStorage(id: string) {
        if (!managers[id]) return
        await apiUpdateTabState(id, managers[id].state)
    }

    return {
        loaded, init, clear, getTab, mainTab, deleteTab, addTab, loadedTabs, selectMainTab, getMainTab, updateTabStateInStorage
    }

})
