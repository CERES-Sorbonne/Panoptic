/**
 * TabStore
 * Keeps all data related to open tabs
 */

import { defineStore } from "pinia";
import { ref } from "vue";
import { TabState } from "./models";
import { TabManager } from "@/core/TabManager";
import { buildTabState, objValues } from "./builder";
import { useProjectStore } from "./projectStore";
import { apiGetTabs, apiSetTabs } from "./apiProjectRoutes";

const TAB_LIST_KEY = 'tab_list'
const TAB_PREFIX = 'tab_id_'
export const TAB_MODEL_VERSION = 6

let managers: { [tabId: number]: TabManager } = {}

export const useTabStore = defineStore('tabStore', () => {
    const loaded = ref(false)
    const mainTab = ref(null)

    const loadedTabs = ref([])

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
        let id = tab.id
        if (loadedTabs.value.includes(id)) {
            console.warn('import tab that already exist. why ?')
            return
        }
        loadedTabs.value.push(tab.id)
        let manager = new TabManager(tab)
        managers[tab.id] = manager
        manager.deactivate()
    }

    function getTab(id: number) {
        return managers[id]
    }

    function getMainTab() {
        return managers[mainTab.value]
    }

    async function loadTabsFromStorage() {
        const tabs = await apiGetTabs()
        const tabList = objValues(tabs)
        const toLoad = []
        for (let tab of tabList) {
            if (!tab || tab.version != TAB_MODEL_VERSION) continue
            toLoad.push(tab)
        }

        for (let tab of toLoad) {
            importTab(tab)
        }

        if (!toLoad.length) {
            await addTab()
        }

        const activeTab = useProjectStore().uiState?.activeTab
        if (activeTab && loadedTabs.value.includes(activeTab)) {
            selectMainTab(activeTab)
        } else {
            selectMainTab(loadedTabs.value[0])
        }
    }

    async function addTab(name?: string, isSelection?: boolean) {
        const tab = buildTabState()
        tab.isSelection = isSelection
        let id = 1
        if (loadedTabs.value.length) {
            let maxId = Math.max(...loadedTabs.value)
            id = maxId + 1
        }
        tab.id = id
        if (name) tab.name = name
        importTab(tab)
        await saveTabsToStorage()
        mainTab.value = id
        managers[id].isNew = true
        selectMainTab(id)
        return tab
    }

    async function deleteTab(id: number) {
        let tabs = loadedTabs.value
        loadedTabs.value = tabs.filter(t => t != id)
        delete managers[id]
        await saveTabsToStorage()
        console.log('locaded tabs', loadedTabs.value)
        console.log('main tab', mainTab.value, id)
        if (mainTab.value == id && loadedTabs.value.length) {
            selectMainTab(loadedTabs.value[0])
        } else if (!loadedTabs.value.length) {
            addTab()
        }
    }

    function selectMainTab(id: number) {
        if (!managers[id]) return

        for (let manager of objValues(managers)) {
            manager.deactivate()
        }

        mainTab.value = id
        managers[id].activate()
        managers[id].update()

        useProjectStore().uiState.activeTab = id
        useProjectStore().saveUiState()
    }

    async function saveTabsToStorage() {
        const tabs = {}
        for (let id of loadedTabs.value) {
            tabs[id] = managers[id].state
        }
        await apiSetTabs(tabs)
    }

    return {
        loaded, init, clear, getTab, mainTab, deleteTab, addTab, loadedTabs, selectMainTab, getMainTab, saveTabsToStorage
    }

})
