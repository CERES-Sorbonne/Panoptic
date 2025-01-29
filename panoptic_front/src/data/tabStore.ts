/**
 * TabStore
 * Keeps all data related to open tabs
 */

import { defineStore } from "pinia";
import { ref } from "vue";
import { TabState } from "./models";
import { TabManager } from "@/core/TabManager";
import { buildTabState } from "./builder";

const TAB_LIST_KEY = 'tab_list'
const TAB_PREFIX = 'tab_id_'
export const TAB_MODEL_VERSION = 1

let managers: {[tabId: number]: TabManager} = {}

export const useTabStore = defineStore('tabStore', () => {

    const loaded = ref(false)
    const mainTab = ref(null)

    const loadedTabs = ref([])

    async function init() {
        loadTabsFromStorage()
        loaded.value = true
    }

    async function clear() {
        loaded.value = false
        mainTab.value = null
        managers = {}
    }

    function importTab(tab: TabState) {
        let id = tab.id
        if(loadedTabs.value.includes(id)) {
            console.warn('import tab that already exist. why ?')
            return
        }
        loadedTabs.value.push(tab.id)
        let manager = new TabManager(tab)
        managers[tab.id] = manager
    }

    function getTab(id: number) {
        return managers[id]
    }

    function getMainTab() {
        return managers[mainTab.value]
    }

    function loadTabsFromStorage() {
        let ids = getSaveTabIdsFromStorage()
        const tabs = []
        for(let id of ids) {
            let tab = getTabFromStorage(id)
            if(!tab || tab.version != TAB_MODEL_VERSION) continue
            tabs.push(tab)
        }

        for(let tab of tabs) {
            importTab(tab)
        }

        if(!tabs.length) {
            addTab()
        }

        selectMainTab(loadedTabs.value[0])
    }

    function addTab(name?: string) {
        const tab = buildTabState()
        let id = 1
        if(loadedTabs.value.length) {
            let maxId = Math.max(...loadedTabs.value)
            id = maxId + 1
        }
        tab.id = id
        if(name) tab.name = name
        importTab(tab)
        saveTabIdsToStorage()
        saveTabToStorage(id)
        mainTab.value = id
        managers[id].isNew = true
        return tab
    }

    function saveTabIdsToStorage() {
        localStorage.setItem(TAB_LIST_KEY, JSON.stringify(loadedTabs.value))
    }

    function saveTabToStorage(id: number) {
        let tab = managers[id]
        const key = TAB_PREFIX + String(id)
        localStorage.setItem(key, JSON.stringify(tab.state))
    }

    function getTabFromStorage(id: number): TabState {
        const key = TAB_PREFIX + String(id)
        let res = localStorage.getItem(key)
        if(res) {
            return JSON.parse(res)
        }
        return undefined
    }

    function getSaveTabIdsFromStorage() {
        let res = localStorage.getItem(TAB_LIST_KEY)
        if(res) {
            return JSON.parse(res)
        } 
        return []
    }

    function deleteTab(id: number) {
        let tabs = loadedTabs.value
        loadedTabs.value = tabs.filter(t => t != id)
        delete managers[id]
        saveTabIdsToStorage()
        if (mainTab.value == id && loadedTabs.value.length) {
            selectMainTab(loadedTabs.value[0])
        } else {
            addTab()
        }
    }

    function selectMainTab(id: number) {
        if(!managers[id]) return
        mainTab.value = id

        managers[id].update()
    }

    return {
        loaded, init, clear, getTab, mainTab, deleteTab, addTab, loadedTabs, selectMainTab, getMainTab, saveTabToStorage
    }

})
