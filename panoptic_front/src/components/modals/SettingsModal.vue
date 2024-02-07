<script setup lang="ts">
import { ModalId } from '@/data/models';
import Modal from './Modal.vue';
import TabMenu from '../TabMenu.vue';
import { onMounted, ref } from 'vue';
import { apiGetPluginsInfo } from '@/data/api';
import PluginSettings from '../PluginSettings.vue';
import { useProjectStore } from '@/data/projectStore';
import ActionSettings from '../ActionSettings.vue';

const project = useProjectStore()

const categories = ref(['general', 'plugins'])
const category = ref(categories.value[0])

const selectedPlugin = ref('')

async function updatePluginInfo() {
    await project.updatePluginInfos()
    selectedPlugin.value = project.data.plugins[0].name
}

</script>

<template>
    <Modal :id="ModalId.SETTINGS" @show="updatePluginInfo">
        <template #title>{{ $t('modals.settings.title') }}</template>
        <template #content>
            <div class="h-100 overflow-scroll">
                <div class="w-100">
                    <TabMenu :options="categories" v-model="category" class="w-100" />
                </div>
                <div v-if="category == 'general'">
                    <ActionSettings :actions="project.actions"/>
                </div>
                <div v-if="category == 'plugins' && selectedPlugin">
                    <TabMenu :options="project.data.plugins.map(info => info.name)" v-model="selectedPlugin" />
                    <div class="p-3" style="max-width: 700px; margin: auto;">
                        <PluginSettings :plugin="project.data.plugins.find(info => info.name == selectedPlugin)" />
                    </div>

                </div>
            </div>

        </template>
    </Modal>
</template>

<style scoped></style>