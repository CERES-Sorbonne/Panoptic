import { InjectionKey } from 'vue'
import { TabManager } from '@/core/TabManager'

/**
 * View-scoped modals: panels centered over the view area instead of over the window.
 *
 * Where a modal is shown depends on the split state:
 * - one view, or two views sharing one filter → over the whole view area (filter bar included)
 * - two views with separate filters           → only over the column (filter bar + view) that opened it
 *
 * Components inside a view learn their view index through `viewModalScopeKey`
 * (provided by ViewPanel / FilterPanel). 'all' targets the whole area whatever
 * the split state (e.g. the selection bar in the top bar). Without a scope, a
 * component keeps its old inline/dropdown behaviour.
 *
 * Targets are found through data attributes set in ProjectView:
 *   data-vm-area="all"    filter bar(s) + views
 *   data-vm-column="i"    filter bar + view i (separate filters)
 */
export type ViewModalScope = number | 'all'

export const viewModalScopeKey: InjectionKey<ViewModalScope> = Symbol('viewModalScope')

export function resolveViewModalTarget(scope: ViewModalScope, tab: TabManager | null): HTMLElement | null {
    const shared = scope === 'all' || !tab || !tab.state.splitView || tab.isBound()
    const selector = shared ? '[data-vm-area="all"]' : `[data-vm-column="${scope}"]`
    return document.querySelector(selector) as HTMLElement | null
}
