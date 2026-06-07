<script setup lang="ts">
/**
 * TabProvider (Pillar D)
 *
 * Renders its slot only once the store is loaded and a manager exists, and keys
 * the subtree by the active tab id so switching tabs fully remounts descendants.
 * This replaces the old `show=false -> nextTick -> reload` remount hack in
 * TabContainer and eliminates stale-capture / null-window errors on tab switch.
 *
 * The active manager is exposed both via the scoped slot (`#default="{ tab }"`)
 * and, for deeper descendants, through `useCurrentTab()`.
 */
import { computed } from 'vue'
import { useTabStore } from '@/data/tabStore'

const tabStore = useTabStore()
const tab = computed(() => tabStore.activeManager)
</script>

<template>
    <div v-if="tabStore.loaded && tab" :key="tabStore.mainTab" class="tab-provider">
        <slot :tab="tab" />
    </div>
</template>

<style scoped>
.tab-provider {
    display: contents;
}
</style>
