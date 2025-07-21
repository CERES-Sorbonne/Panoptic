<script setup lang="ts">
import { ModalId } from '@/data/models';
import { ref, watch } from 'vue';
import { useProjectStore } from '@/data/projectStore';
import PageWindow from '../utils/PageWindow.vue';
import Modal2 from './Modal2.vue';
import VectorSettings from '../settings/VectorSettings.vue';
import PluginSettingsWindow from '../settings/PluginSettingsWindow.vue';
import ImageSettings from '../settings/ImageSettings.vue';

const project = useProjectStore()

const pageElem = ref(null)

enum PAGE {
    Images = 'images',
    Vectors = 'vectors',
    Plugins = 'plugins',
}

const options = ref(Object.values(PAGE))
const selectedPage = ref('')
const changed = ref(false)

const selectedPlugin = ref('')

async function updatePluginInfo() {
    await project.updatePluginInfos()
    if(project.data.plugins.length == 0) return
    
    selectedPlugin.value = project.data.plugins[0].name
    // delete browser Cache to update image routes
    // if not the browser will continue loading raw pictures after adding miniatures for example
    caches.keys().then((keyList) => Promise.all(keyList.map((key) => caches.delete(key))))
}

function applyChange() {
    if(pageElem.value) {
        pageElem.value.apply()
    }
}

function cancelChange() {
    if(pageElem.value) {
        pageElem.value.cancel()
    }
}

watch(selectedPage, () => changed.value = false)

</script>

<template>
    <Modal2 :id="ModalId.SETTINGS" @show="updatePluginInfo">
        <template #title>{{ $t('modals.settings.title') }}</template>
        <template #content>
            <div class="h-100 overflow-hidden">
                <PageWindow :options="options" v-model:page="selectedPage">
                    <template #header>
                        <div v-if="changed" class="d-flex">
                            <div class="h-100 ms-2" style="border-left: 1px solid var(--border-color);"></div>
                            <div class="bb ms-3 text-success" @click="applyChange">Apply</div>
                            <div class="bb ms-3 text-danger" @click="cancelChange">Cancel</div>
                        </div>
                    </template>
                    <template #default="{ page }">
                        <div v-if="page == ''" class="h-100 w-100">
                            <div class="d-flex flex-wrap h-100 justify-content-center">
                                <div class="bb align-self-center m-4" style="width: 120px;"
                                    @click="selectedPage = PAGE.Images">
                                    <div class="border rounded p-2 text-center">
                                        <div><i class="bi bi-images" style="font-size: 50px;" /></div>
                                        <div>Images</div>
                                    </div>
                                </div>

                                <div class="bb align-self-center m-4" style="width: 120px;"
                                    @click="selectedPage = PAGE.Vectors">
                                    <div class="border rounded p-2 text-center">
                                        <div><i class="bi bi-arrow-left-right" style="font-size: 50px;" /></div>
                                        <div>Vectors</div>
                                    </div>
                                </div>

                                <div class="bb align-self-center m-4" style="width: 120px;"
                                    @click="selectedPage = PAGE.Plugins">
                                    <div class="border rounded p-2 text-center">
                                        <div><i class="bi bi-plugin" style="font-size: 50px;" /></div>
                                        <div>Plugins</div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <ImageSettings v-if="page == PAGE.Images" v-model:changed="changed" ref="pageElem"/>
                        <VectorSettings v-if="page == PAGE.Vectors" />
                        <PluginSettingsWindow v-if="page == PAGE.Plugins" v-model:changed="changed" ref="pageElem"/>
                    </template>
                </PageWindow>
                <!-- <div class="w-100">
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
                </div> -->
            </div>

        </template>
    </Modal2>
</template>

<style scoped></style>