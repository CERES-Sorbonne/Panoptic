<script setup lang="ts">
/**
 * Gives its children the active tab manager.
 *
 * The slot is rendered only when the store is loaded and a manager exists, so
 * children never have to handle a missing tab. The subtree is keyed by the
 * active tab id: switching tabs remounts everything inside, which avoids
 * children keeping values from the previous tab.
 *
 * The manager is available through the scoped slot (`#default="{ tab }"`), and
 * deeper descendants can also read it with `useCurrentTab()`.
 */
import { computed } from 'vue'
import { useTabStore } from '@/data/stores/tabStore'

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
