<script setup lang="ts">
import { TabManager } from '@/core/TabManager';
import { useProjectStore } from '@/data/projectStore';
import { defineProps, provide, watch } from 'vue'

const project = useProjectStore()

const props = defineProps<{
    tabId: number
}>()

const tabManager = new TabManager(project.data.tabs[props.tabId])
provide('tabManager', tabManager)

watch(() => props.tabId, () => tabManager.load(project.data.tabs[props.tabId]))
watch(tabManager.state, (state) => {
    project.updateTabs()
}, { deep: true })
</script>

<template>
    <slot></slot>
</template>