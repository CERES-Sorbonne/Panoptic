<script setup lang="ts">

import { ModalId } from '../../data/models';
import { ref, watch, computed, openBlock } from 'vue';
import PropertyOptions from './PropertyOptions.vue';
import wTT from '../tooltips/withToolTip.vue';
import FolderList2 from '../foldertree/FolderList2.vue';
import { useProjectStore } from '@/data/projectStore';
import { usePanopticStore } from '@/data/panopticStore';
import { goNext, objValues } from '@/utils/utils';
import TaskStatus from './TaskStatus.vue';
import { deletedID, useDataStore } from '@/data/dataStore';
import PropertyGroup from './PropertyGroup.vue';
import TabContainer from '../TabContainer.vue';
import { useTabStore } from '@/data/tabStore';
import DraggablePropertyList from './DraggablePropertyList.vue';

const BASE_WIDTH = 200
const SMALL_WIDTH = 55

const project = useProjectStore()
const data = useDataStore()
const panoptic = usePanopticStore()
const tabStore = useTabStore()


const emits = defineEmits(['export', 'toggle'])

const showImport = ref(false)
const isUploading = ref(false)


const menuOpen = ref(true)
const menuWidth = computed(() => menuOpen.value ? BASE_WIDTH : SMALL_WIDTH)

const propertiesWithoutGroup = computed(() => data.propertyList.filter(p => p.id >= 0 && (p.propertyGroupId === undefined || !data.propertyGroups[p.propertyGroupId])))

const handleInput = async (e: any) => {
    panoptic.showModal(ModalId.IMPORT)
}

const tasks = computed(() => project.backendStatus.tasks.filter(t => !(t.done)))

function promptFolder() {
    panoptic.showModal(ModalId.FOLDERSELECTION, { callback: addFolder, mode: "images" })
}

function addFolder(path) {
    if (!path) return
    data.addFolder(path)
}

function toggleMenu() {
    menuOpen.value = !menuOpen.value
    emits('toggle')
}

watch(() => project.status.import.to_import, () => showImport.value = true)

</script>

<template>
    <TabContainer :id="tabStore.mainTab">
        <template #default="{ tab }">
            <div class="menu overflow-scroll" :style="{ width: menuWidth + 'px' }">
                <div class="">
                    <div>
                        <div class="m-0" style="padding: 4px 0px 4px 8px">
                            <div class="d-flex align-items-center" style="font-size: 15px; line-height: 14px;">
                                <template v-if="menuOpen">
                                    <div class="flex-grow-1 text-capitalize overflow-hidden">{{
                                        panoptic.data.status.selectedProject?.name }}
                                    </div>
                                    <wTT message="main.menu.close_project">
                                        <div class="base-hover p-1" @click="panoptic.closeProject()"><i
                                                class="bi bi-arrow-up-left-square red-hover"></i></div>
                                    </wTT>
                                    <div class="base-hover p-1" @click="panoptic.showModal(ModalId.SETTINGS)"><i
                                            class="bi bi-gear"></i>
                                    </div>
                                </template>
                                <div class="base-hover p-1" :class="menuOpen ? '' : 'flex-grow-1 text-center'"
                                    style="margin-right: 6px;" @click="toggleMenu">
                                    <i v-if="menuOpen" class="bi bi-chevron-left"></i>
                                    <i v-else class="bi bi-chevron-right" />
                                </div>

                            </div>
                        </div>
                        <template v-if="menuOpen">
                            <div class="custom-hr" />
                            <div class="ps-2 pe-2" style="padding-bottom: 9.5px">
                                <div class="d-flex align-items-center">
                                    <div><b>{{ $t('main.nav.folders.title') }}</b></div>
                                    <div id="add_folder" class="ms-auto plus" @click="promptFolder(); goNext();">
                                        <wTT message="main.nav.folders.add"><i class="bi bi-plus"></i></wTT>
                                    </div>
                                </div>
                                <div style="max-height: 300px; overflow: auto;">
                                    <FolderList2 :folders="data.folderRoots"
                                        :filter-manager="tab.collection.filterManager"
                                        :visible-folders="tab.state.visibleFolders" :tab="tab" />
                                </div>

                            </div>
                        </template>
                        <template v-if="menuOpen">
                            <div id="import" v-if="tasks && tasks.length">
                                <div class="custom-hr" />

                                <div class="pt-1 pb-2">
                                    <div class="d-flex align-items-center ps-2 pe-2 " style="height: 30px;">
                                        <div><b>{{ $t('main.nav.tasks.title') }}</b></div>
                                    </div>
                                    <div class="custom-hr" />
                                    <div v-if="project.backendStatus" class="ps-2 pe-2">
                                        <div v-for="task, i in tasks" class="p-1">
                                            <div v-if="i" class="custom-hr" />
                                            <TaskStatus :task="task" />
                                        </div>
                                    </div>
                                </div>

                            </div>
                        </template>

                        <div class="custom-hr" />
                        <div class="p-1 mt-0">
                            <template v-if="menuOpen">
                                <div class="d-flex p-1">
                                    <wTT message="main.nav.properties.properties_tooltip" pos="top" :icon=true><b>{{
                                        $t('main.nav.properties.title') }}</b></wTT>
                                    <span class="flex-grow-1"></span>
                                    <span v-if="isUploading" class="spinner-grow spinner-grow-sm float-end"
                                        style="width:10px;height:10px;margin-top:5px;">
                                        <span class="sr-only" />
                                    </span>
                                    <span v-else class="bb me-1">
                                        <wTT pos="right" message="main.nav.properties.import_properties_tooltip">
                                            <i class="bi bi-box-arrow-in-up text-secondary"
                                                style="position: relative; top:0px; font-size: 15px;"
                                                @click="handleInput" />
                                        </wTT>
                                    </span>
                                    <span class="bb me-2">
                                        <wTT pos="right" message="main.nav.properties.export_properties_tooltip"><i
                                                class="bi bi-box-arrow-up text-secondary"
                                                style="position: relative; top: 0px; font-size: 15px;"
                                                @click="panoptic.showModal(ModalId.EXPORT, undefined)" /></wTT>
                                    </span>
                                </div>
                            </template>
                            <div class="mt-2" v-if="project.status.loaded">
                                <!-- <div v-for="group in objValues(data.propertyGroups)" style="padding-left: 0px;">
                                    <PropertyGroup :tab="tab" :group="group" class="mb-1" :menu-open="menuOpen" />
                                </div>
                                <div v-for="property in propertiesWithoutGroup" class="ps-1 pe-1">
                                    <div class="property-item" v-if="property.id >= 0">
                                        <PropertyOptions :tab="tab" :property="property" :open="menuOpen" />
                                    </div>
                                </div> -->
                                <DraggablePropertyList :tab="tab" :menu-open="menuOpen"></DraggablePropertyList>


                                <template v-if="menuOpen">
                                    <div class="property-item m-0 p-0"></div>
                                    <div id="add-property"
                                        @click="panoptic.showModal(ModalId.PROPERTY, undefined); goNext()"
                                        class="btn-icon base-hover mt-1" style="line-height: 25px;">
                                        <i class="bi bi-plus btn-icon float-start" style="font-size: 25px;"></i>
                                        <span>{{ $t('main.nav.properties.add_property') }}</span>
                                    </div>
                                    <div class="custom-hr mt-1" />
                                    <div @click="data.addPropertyGroup('New Group')" class="btn-icon base-hover mt-1"
                                        style="line-height: 25px;">
                                        <i class="bi bi-plus btn-icon float-start" style="font-size: 25px;"></i>
                                        <span>{{ $t('main.nav.properties.add_property_group') }}</span>
                                    </div>
                                </template>
                            </div>
                        </div>

                        <!-- <div class="custom-hr" />

                        <div class="p-2 mt-0">
                            <template v-if="menuOpen">
                                <wTT message="main.nav.computed.computed_tooltip" :icon="true"><b>{{
                                    $t("main.nav.computed.title")
                                        }}</b></wTT>
                            </template>
                            <div class="mt-2" v-if="project.status.loaded">
                                <template v-for="property in data.properties">
                                    <div class="property-item" v-if="property.id < 0 && property.id != deletedID">
                                        <wTT pos="bottom"
                                            :message="'main.nav.computed.' + Math.abs(property.id).toString() + '_tooltip'">
                                            <PropertyOptions :tab="tab" :property="property" :open="menuOpen" />
                                        </wTT>
                                    </div>
                                </template>
                            </div>
                        </div> -->
                    </div>
                </div>
            </div>
        </template>
    </TabContainer>
</template>

<style scoped>
.plus {
    font-size: 1.5em;
}

.plus:hover {
    cursor: pointer;
}

.menu {
    font-size: 13px;
    height: 100vh;
    /* position: sticky; */
    /* position: relative; */
    top: 0;
    border-right: 1px solid var(--border-color);
    -ms-overflow-style: none;
    /* IE and Edge */
    scrollbar-width: none;
    /* Firefox */
    overflow-y: scroll;
}

.menu::-webkit-scrollbar {
    display: none;
}


.menu b {
    font-size: 13px;
}

.menu h3,
.menu .h3 {
    font-size: 1.1rem;
    margin-left: 1rem;
}

.red-hover:hover {
    color: red;
}
</style>