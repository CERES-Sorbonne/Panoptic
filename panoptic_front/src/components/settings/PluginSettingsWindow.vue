<script setup lang="ts">
import { ref, computed } from 'vue'
import PageWindow from '../utils/PageWindow.vue';
import { useProjectStore } from '@/data/stores/projectStore';
import PluginSettings from './PluginSettings.vue';

const project = useProjectStore()

const selectedPage = ref(project.state.plugins[0]?.name ?? '')

const options = computed(() => project.state.plugins.map(p => p.name))
</script>

<template>
    <PageWindow :options="options" v-model:page="selectedPage">
        <template #default="{ page }">
            <PluginSettings v-if="page" :plugin="project.state.plugins.find(p => p.name == page)" />
        </template>
    </PageWindow>
</template>
