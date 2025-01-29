<script setup lang="ts">
import { TabManager } from '@/core/TabManager';
import { useTabStore } from '@/data/tabStore';
import { nextTick, onMounted, ref, watch } from 'vue';

const tabStore = useTabStore()

const props = defineProps<{
    id?: number
}>()

let tab: TabManager
const show = ref(false)

function loadTab() {
    tab = tabStore.getTab(props.id)
    show.value = true
}

onMounted(loadTab)
watch(() => props.id, async () => {
    show.value = false
    await nextTick()
    loadTab()
})
</script>

<template>
    <slot v-if="show && tabStore.loaded" :tab="tab"></slot>
</template>

<style scoped></style>