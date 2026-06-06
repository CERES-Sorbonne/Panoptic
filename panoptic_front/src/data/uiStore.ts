/**
 * UI Store - Manages all UI state (panels, resizes, layout)
 * Persists UI preferences to backend using project store's apiSetUIData
 */

import { defineStore } from 'pinia'
import { reactive, watch, ref } from 'vue'
import { apiGetUIData, apiSetUIData } from './apiProjectRoutes'
import { UIDataKeys } from './models'
import { deepCopy } from '@/utils/utils'

console.log('[uiStore] Module loaded')

export type BottomPanel = 'properties' | 'export' | null

export interface PanelStates {
    leftPanelOpen: boolean
    rightPanelOpen: boolean
    showSplitView: boolean
    viewSplitEnabled: boolean
    viewsLinked: boolean
    activeBottomPanel: BottomPanel
}

export interface ResizeStates {
    splitRowSecondaryHeight: number
    splitColumnSecondaryWidth: number
    leftSidebarWidth: number
    foldersHeight: number
    propertiesHeight: number
    mainSplitRatio: number
}

export interface ScrollStates {
    leftPanelScrollX: number
    leftPanelScrollY: number
    rightPanelScrollX: number
    rightPanelScrollY: number
}

export const useUiStore = defineStore('uiStore', () => {
    const loaded = ref(false)

    const panelStates = reactive<PanelStates>({
        leftPanelOpen: true,
        rightPanelOpen: true,
        showSplitView: true,
        viewSplitEnabled: false,
        viewsLinked: false,
        activeBottomPanel: 'properties'
    })

    const resizeStates = reactive<ResizeStates>({
        splitRowSecondaryHeight: 200,
        splitColumnSecondaryWidth: 300,
        leftSidebarWidth: 280,
        foldersHeight: 250,
        propertiesHeight: 250,
            mainSplitRatio: 0.5
    })

    const scrollStates = reactive<ScrollStates>({
        leftPanelScrollX: 0,
        leftPanelScrollY: 0,
        rightPanelScrollX: 0,
        rightPanelScrollY: 0
    })

    // Watch for changes and save to backend (only after loaded)
    watch(() => ({
        panelStates: deepCopy(panelStates),
        resizeStates: deepCopy(resizeStates),
        scrollStates: deepCopy(scrollStates)
    }), async (layoutState) => {
        if (!loaded.value) return

        try {
            console.log('[uiStore] Saving layout state:', layoutState)
            const uiState = (await apiGetUIData(UIDataKeys.STATE)) || {}
            uiState.layout = layoutState
            const result = await apiSetUIData(UIDataKeys.STATE, uiState)
            console.log('[uiStore] Saved successfully:', result)
        } catch (e) {
            console.error('[uiStore] Failed to save UI layout state:', e)
        }
    }, { deep: true })

    async function init() {
        try {
            console.log('[uiStore] Loading UI layout state from backend...')
            const uiState = await apiGetUIData(UIDataKeys.STATE)
            console.log('[uiStore] Loaded uiState:', uiState)

            if (uiState?.layout) {
                const layout = uiState.layout
                console.log('[uiStore] Applying layout:', layout)
                if (layout.panelStates) {
                    Object.assign(panelStates, layout.panelStates)
                }
                if (layout.resizeStates) {
                    Object.assign(resizeStates, layout.resizeStates)
                }
                if (layout.scrollStates) {
                    Object.assign(scrollStates, layout.scrollStates)
                }
                console.log('[uiStore] Layout state loaded successfully')
            } else {
                console.log('[uiStore] No layout state found in backend, using defaults')
            }
        } catch (e) {
            console.error('[uiStore] Failed to load UI layout state from backend:', e)
        } finally {
            loaded.value = true
            console.log('[uiStore] Init complete, ready to render')
        }
    }

    function setPanelState(key: keyof PanelStates, value: boolean) {
        panelStates[key] = value
    }

    function setResizeState(key: keyof ResizeStates, value: number) {
        resizeStates[key] = value
    }

    function setScrollState(key: keyof ScrollStates, value: number) {
        scrollStates[key] = value
    }

    function reset() {
        Object.assign(panelStates, {
            leftPanelOpen: true,
            rightPanelOpen: true,
            showSplitView: true,
            viewSplitEnabled: false,
            viewsLinked: false,
            activeBottomPanel: 'properties'
        })
        Object.assign(resizeStates, {
            splitRowSecondaryHeight: 200,
            splitColumnSecondaryWidth: 300,
            leftSidebarWidth: 280,
            foldersHeight: 250,
            propertiesHeight: 250,
        mainSplitRatio: 0.5
        })
        Object.assign(scrollStates, {
            leftPanelScrollX: 0,
            leftPanelScrollY: 0,
            rightPanelScrollX: 0,
            rightPanelScrollY: 0
        })
        loaded.value = false
    }

    return {
        // State
        loaded,
        panelStates,
        resizeStates,
        scrollStates,
        // Functions
        init,
        setPanelState,
        setResizeState,
        setScrollState,
        reset
    }
})
