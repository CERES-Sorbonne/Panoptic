<script setup lang="ts">
import { ModalId } from '@/data/models';
import Modal from './Modal.vue';
import TabMenu from '../TabMenu.vue';
import { ref } from 'vue';
import PluginSettings from '../settings/PluginSettings.vue';
import { useProjectStore } from '@/data/projectStore';
import GeneralSettings from '../settings/GeneralSettings.vue';
import { useDataStore } from '@/data/dataStore';

const project = useProjectStore()

const categories = ref(['general', 'plugins'])
const category = ref(categories.value[0])



const selectedPlugin = ref('')

async function updatePluginInfo() {
    await project.updatePluginInfos()
    selectedPlugin.value = project.data.plugins[0].name
    // delete browser Cache to update image routes
    // if not the browser will continue loading raw pictures after adding miniatures for example
    caches.keys().then((keyList) => Promise.all(keyList.map((key) => caches.delete(key))))
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
                    <GeneralSettings />
                    <div>
                        <span class="bbb" @click="useDataStore().deleteEmptyClones()"> Delete Empty Clones</span>
                    </div>
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