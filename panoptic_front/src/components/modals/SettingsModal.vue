<script setup lang="ts">
import { ModalId } from '@/data/models';
import Modal from './Modal.vue';
import TabMenu from '../TabMenu.vue';
import { onMounted, ref } from 'vue';
import { apiGetPluginsInfo } from '@/data/api';
import PluginSettings from '../PluginSettings.vue';


const categories = ref(['general', 'plugins'])
const category = ref(categories.value[1])

const pluginsInfo = ref([])
const selectedPlugin = ref('')

async function updatePluginInfo() {
    pluginsInfo.value = await apiGetPluginsInfo()
    selectedPlugin.value = pluginsInfo.value[0].name
}

</script>

<template>
    <Modal :id="ModalId.SETTINGS" @show="updatePluginInfo">
        <template #title>{{ $t('modals.settings.title') }}</template>
        <template #content>
            <div class="w-100">
                <TabMenu :options="categories" v-model="category" class="w-100" />
            </div>
            <div v-if="category == 'general'">

            </div>
            <div v-if="category == 'plugins' && selectedPlugin">
                <TabMenu :options="pluginsInfo.map(info => info.name)" v-model="selectedPlugin" />
                <div class="p-3" style="max-width: 700px; margin: auto;">
                    <PluginSettings :plugin="pluginsInfo.find(info => info.name == selectedPlugin)" />
                </div>

            </div>
        </template>
    </Modal>
</template>

<style scoped></style>