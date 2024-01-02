<script setup lang="ts">

import { ModalId } from '../../data/models';
import { ref, defineEmits } from 'vue';
import PropertyOptions from './PropertyOptions.vue';
import wTT from '../tooltips/withToolTip.vue';
import { sleep } from '@/utils/utils';
import FolderList2 from '../foldertree/FolderList2.vue';
import { useProjectStore } from '@/data/projectStore';
import router from '@/router';
import { usePanopticStore } from '@/data/panopticStore';

const store = useProjectStore()
const panoptic = usePanopticStore()
const tabManager = store.getTabManager()

const emits = defineEmits(['export'])


const inputFile = ref(null)
const isUploading = ref(false)

const handleInput = async (e: any) => {
    isUploading.value = true
    console.log(isUploading.value)
    const file = e.target.files[0]
    let res = await store.uploadPropFile(file)
    isUploading.value = false
}

</script>

<template>
    <div class="menu overflow-scroll">
        <div class="">
            <div>
                <div class="m-0" style="padding: 4px 0px 4px 8px">
                    <div class="d-flex align-items-center" style="font-size: 15px; line-height: 14px;">
                        <div class="flex-grow-1">{{ panoptic.data.status.selectedProject.name }}</div>
                        <div class="base-hover p-1" style="margin-right: 6px;" @click="panoptic.closeProject()"><i class="bi bi-x"></i></div>
                    </div>
                </div>
                <div class="custom-hr" />
                <div class="ps-2 pe-2" style="padding-bottom: 9.5px">
                    <div class="d-flex align-items-center">
                        <div><b>{{ $t('main.nav.folders.title') }}</b></div>
                        <div class="ms-auto plus" @click="panoptic.showModal(ModalId.FOLDERSELECTION)">
                            <wTT message="main.nav.folders.add"><i class="bi bi-plus"></i></wTT>
                        </div>
                    </div>

                    <!-- <FolderList v-if="globalStore.tabs[globalStore.selectedTab]" :folders="globalStore.folderTree"
                        :tab="globalStore.tabs[globalStore.selectedTab].data" /> -->
                    <FolderList2 v-if="store.getTab()" :folders="store.folderRoots"
                        :filter-manager="tabManager.collection.filterManager"
                        :visible-folders="tabManager.state.visibleFolders" />
                </div>
                <div class="p-2"
                    v-if="store.status.import.to_import != undefined && store.status.import.to_import > 0">
                    <div class="w-100 text-center" style="font-size: 10px;">
                        {{ store.status.import.imported }} / {{ store.status.import.to_import }} importées
                    </div>
                    <div v-if="store.status.import.to_import > 0" class="progress" role="progressbar"
                        aria-label="Example 1px high" aria-valuemin="0" aria-valuemax="100" style="height: 1px">
                        <div class="progress-bar"
                            :style="`width: ${store.status.import.imported / store.status.import.to_import * 100}%`">
                        </div>
                    </div>
                </div>
                <div class="p-2"
                    v-if="store.status.import.to_import != undefined && store.status.import.to_import > 0">
                    <div class="w-100 text-center" style="font-size: 10px;">
                        {{ store.status.import.computed }} / {{ store.status.import.to_import }} computed
                    </div>
                    <div v-if="store.status.import.to_import > 0" class="progress" role="progressbar"
                        aria-label="Example 1px high" aria-valuemin="0" aria-valuemax="100" style="height: 1px">
                        <div class="progress-bar"
                            :style="`width: ${store.status.import.computed / store.status.import.to_import * 100}%`">
                        </div>
                    </div>
                </div>
                <div class="custom-hr" />
                <div class="p-2 mt-0">
                    <div class="d-flex">
                        <wTT message="main.nav.properties.properties_tooltip" pos="top" :icon=true><b>{{
                            $t('main.nav.properties.title') }}</b></wTT>
                        <span class="flex-grow-1"></span>
                        <span v-if="isUploading" class="spinner-grow spinner-grow-sm float-end"
                            style="width:10px;height:10px;margin-top:5px;">
                            <span class="sr-only" />
                        </span>
                        <span v-else class="me-3">
                            <input type="file" ref="inputFile" accept="text/csv" @change="handleInput" hidden />
                            <wTT pos="right" message="main.nav.properties.import_properties_tooltip"><i
                                    class="bi bi-file-earmark-arrow-up btn-icon text-secondary"
                                    @click="inputFile.click()" /></wTT>
                        </span>
                        <span class="me-3">
                            <wTT pos="right" message="main.nav.properties.export_properties_tooltip"><i
                                    class="bi bi-box-arrow-down btn-icon text-secondary" @click="panoptic.showModal(ModalId.EXPORT, undefined)" /></wTT>
                        </span>
                    </div>

                    <!-- <i class="bi bi-plus btn-icon float-end" style="font-size: 25px;"></i> -->
                    <div class="mt-2" v-if="store.status.loaded">
                        <template v-for="property in store.data.properties">
                            <div class="property-item" v-if="property.id >= 0">
                                <!-- <TagProperty
                                    v-if="property.type == models.PropertyType.multi_tags || property.type == models.PropertyType.tag"
                                    :data="property" />
                                <Property v-else :data="property" /> -->
                                <PropertyOptions :property="property" />
                            </div>
                        </template>
                        <div class="property-item m-0 p-0"></div>
                        <div @click="panoptic.showModal(ModalId.PROPERTY, undefined)" class="btn-icon base-hover mt-1"
                            style="line-height: 25px;">
                            <i class="bi bi-plus btn-icon float-start" style="font-size: 25px;"></i>
                            <span>{{ $t('main.nav.properties.add_property') }}</span>
                        </div>
                    </div>
                </div>

                <div class="custom-hr" />
                <div class="p-2 mt-0">
                    <wTT message="main.nav.computed.computed_tooltip" :icon="true"><b>{{ $t("main.nav.computed.title")
                    }}</b></wTT>
                    <div class="mt-2" v-if="store.status.loaded">
                        <template v-for="property in store.data.properties">
                            <div class="property-item" v-if="property.id < 0">
                                <wTT pos="bottom"
                                    :message="'main.nav.computed.' + Math.abs(property.id).toString() + '_tooltip'">
                                    <PropertyOptions :property="property" />
                                </wTT>
                            </div>
                        </template>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.plus{
    font-size: 1.5em;
}
.plus:hover{
    cursor: pointer;
}
</style>