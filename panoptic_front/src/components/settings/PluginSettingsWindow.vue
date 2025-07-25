<script setup lang="ts">
import { defineProps, defineEmits, ref, computed } from 'vue'
import PageWindow from '../utils/PageWindow.vue';
import { PluginDescription } from '@/data/models';
import { useProjectStore } from '@/data/projectStore';
import PluginSettings from './PluginSettings.vue';

const props = defineProps<{}>()
const emits = defineEmits([])


const project = useProjectStore()

const selectedPage = ref(project.data.plugins[0]?.name ?? '')
const changed = false

const options = computed(() => project.data.plugins.map(p => p.name))

function applyChange() {

}

function cancelChange() {

}
</script>

<template>
    <PageWindow :options="options" v-model:page="selectedPage">
        <template #header>
            <div v-if="changed" class="d-flex">
                <div class="h-100 ms-2" style="border-left: 1px solid var(--border-color);"></div>
                <div class="bb ms-3 text-success" @click="applyChange">{{$t('modals.settings.apply')}}</div>
                <div class="bb ms-3 text-danger" @click="cancelChange">{{$t('modals.settings.cancel')}}</div>
            </div>
        </template>
        <template #default="{ page }">
            <div class="">
                <PluginSettings v-if="page" :plugin="project.data.plugins.find(p => p.name == page)" />
            </div>
        </template>
    </PageWindow>
</template>

<style scoped>
.settings-content {
  flex: 1 1 auto;
  overflow-y: auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
</style>