import { InjectionKey, ref, watch } from 'vue'
import { TabManager } from '@/core/TabManager'

/**
 * View-scoped modals: panels centered over the view area instead of over the window.
 *
 * Where a modal is shown depends on the split state:
 * - one view, or two views sharing one filter → over the whole view area
 * - two views with separate filters           → only over the view that opened it
 *
 * Components inside a view learn their view index through `viewModalScopeKey`
 * (provided by ViewPanel / FilterPanel). 'all' targets the whole area whatever
 * the split state (e.g. the selection bar in the top bar). Without a scope, a
 * component keeps its old inline/dropdown behaviour.
 *
 * Targets are found through data attributes set in ProjectView / ViewPanel:
 *   data-vm-area="all"    filter bar(s) + views
 *   data-vm-area="views"  views only
 *   data-vm-column="i"    filter bar + view i (separate filters)
 *   data-vm-view="i"      view i only
 */
export type ViewModalScope = number | 'all'

export const viewModalScopeKey: InjectionKey<ViewModalScope> = Symbol('viewModalScope')

const STORAGE_KEY = 'panoptic.viewModal.coverFilters'

function readCoverFilters(): boolean {
    try {
        return localStorage.getItem(STORAGE_KEY) !== 'false'
    } catch {
        return true
    }
}

// Whether the modal also covers the filter bar(s), or only the views below.
export const viewModalCoverFilters = ref(readCoverFilters())
watch(viewModalCoverFilters, (v) => {
    try { localStorage.setItem(STORAGE_KEY, String(v)) } catch { /* ignore */ }
})

export function resolveViewModalTarget(scope: ViewModalScope, tab: TabManager | null): HTMLElement | null {
    const cover = viewModalCoverFilters.value
    const shared = scope === 'all' || !tab || !tab.state.splitView || tab.isBound()
    const selector = shared
        ? `[data-vm-area="${cover ? 'all' : 'views'}"]`
        : cover ? `[data-vm-column="${scope}"]` : `[data-vm-view="${scope}"]`
    return document.querySelector(selector) as HTMLElement | null
}
