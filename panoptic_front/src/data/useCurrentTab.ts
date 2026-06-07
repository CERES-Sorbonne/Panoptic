import { computed, ComputedRef } from 'vue'
import { useTabStore } from './tabStore'
import { TabManager } from '@/core/TabManager'

/**
 * Reactive handle to the current (active) tab's TabManager (Pillar D).
 *
 * Returns a ComputedRef that tracks `mainTab`, so components stay correct across
 * tab switches instead of capturing a stale manager once at setup. Works without
 * a provider ancestor; pair with TabProvider's `:key` remount when a component
 * subtree must be fully reset on tab change.
 */
export function useCurrentTab(): ComputedRef<TabManager | null> {
    const tabStore = useTabStore()
    return computed(() => tabStore.activeManager)
}
