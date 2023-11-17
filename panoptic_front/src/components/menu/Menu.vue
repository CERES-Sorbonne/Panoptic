<script setup lang="ts">

import { globalStore } from '../../data/store';
import { apiExportProperties } from '../../data/api';
import { Modals } from '../../data/models';
import { ref, defineEmits } from 'vue';
import FolderList from '../foldertree/FolderList.vue';
import PropertyOptions from './PropertyOptions.vue';
import wTT  from '../tooltips/withToolTip.vue';
import { sleep } from '@/utils/utils';

const emits = defineEmits(['export'])


const inputFile = ref(null)
const isUploading = ref(false)

const handleInput = async (e: any) => {
    isUploading.value = true
    console.log(isUploading.value)
    const file = e.target.files[0]
    let res = await globalStore.uploadPropFile(file)
    // THIS IS TAKING WAY LONGER THAN THE REAL API CALL, WHY??
    if(res){
        isUploading.value = false
        await sleep(10) // let vue have time to actualise the uploading visual effect
        // HOW TO REFRESH ALL COMPONENTS DEPENDING ON NEW DATA ??
        globalStore.fetchAllData()
    }
    else{
        // make a code for import error logo
    }
}

</script>

<template>
    <div class="menu overflow-scroll">
        <div class="">
            <div>
                <div class="ps-2 pe-2" style="padding-bottom: 9.5px; padding-top: 5px;">
                    <div class="d-flex">
                        <div><b>{{ $t('main.nav.folders.title') }}</b></div>
                        <!-- <div class="ms-auto" @click="globalStore.showModal(Modals.FOLDERTOPROP)">
                            <i class="bi bi-three-dots"></i>
                        </div> -->
                    </div>

                    <FolderList v-if="globalStore.tabs[globalStore.selectedTab]" :folders="globalStore.folderTree"
                        :tab="globalStore.tabs[globalStore.selectedTab].data" />
                </div>
                <div class="p-2"
                    v-if="globalStore.importState.to_import != undefined && globalStore.importState.to_import > 0">
                    <div class="w-100 text-center" style="font-size: 10px;">
                        {{ globalStore.importState.imported }} / {{ globalStore.importState.to_import }} importées
                    </div>
                    <div v-if="globalStore.importState.to_import > 0" class="progress" role="progressbar"
                        aria-label="Example 1px high" aria-valuemin="0" aria-valuemax="100" style="height: 1px">
                        <div class="progress-bar"
                            :style="`width: ${globalStore.importState.imported / globalStore.importState.to_import * 100}%`">
                        </div>
                    </div>
                </div>
                <div class="p-2"
                    v-if="globalStore.importState.to_import != undefined && globalStore.importState.to_import > 0">
                    <div class="w-100 text-center" style="font-size: 10px;">
                        {{ globalStore.importState.computed }} / {{ globalStore.importState.to_import }} computed
                    </div>
                    <div v-if="globalStore.importState.to_import > 0" class="progress" role="progressbar"
                        aria-label="Example 1px high" aria-valuemin="0" aria-valuemax="100" style="height: 1px">
                        <div class="progress-bar"
                            :style="`width: ${globalStore.importState.computed / globalStore.importState.to_import * 100}%`">
                        </div>
                    </div>
                </div>
                <div class="custom-hr" />
                <div class="p-2 mt-0">
                    <wTT message="main.nav.properties.properties_tooltip" pos="top" :icon=true><b>{{ $t('main.nav.properties.title') }}</b></wTT>
                    <span v-if="isUploading" class="spinner-grow spinner-grow-sm float-end" style="width:10px;height:10px;margin-top:5px;">
                        <span class="sr-only"/>
                    </span>
                    <span v-else class="float-end me-3">
                        <input type="file" ref="inputFile" accept="text/csv" @change="handleInput" hidden/>
                        <wTT pos="right" message="main.nav.properties.import_properties_tooltip"><i class="bi bi-file-earmark-arrow-up btn-icon text-secondary" @click="inputFile.click()"/></wTT>
                    </span>
                    <span class="float-end me-3">
                        <wTT pos="right" message="main.nav.properties.export_properties_tooltip"><i class="bi bi-box-arrow-down btn-icon text-secondary" @click="emits('export')"/></wTT>
                    </span>
                    <!-- <i class="bi bi-plus btn-icon float-end" style="font-size: 25px;"></i> -->
                    <div class="mt-2" v-if="globalStore.isLoaded">
                        <template v-for="property in globalStore.properties">
                            <div class="property-item" v-if="property.id >= 0">
                                <!-- <TagProperty
                                    v-if="property.type == models.PropertyType.multi_tags || property.type == models.PropertyType.tag"
                                    :data="property" />
                                <Property v-else :data="property" /> -->
                                <PropertyOptions :property="property" />
                            </div>
                        </template>
                        <div class="property-item m-0 p-0"></div>
                        <div @click="globalStore.showModal(Modals.PROPERTY)" class="btn-icon base-hover mt-1"
                            style="line-height: 25px;">
                            <i class="bi bi-plus btn-icon float-start" style="font-size: 25px;"></i>
                            <span>{{ $t('main.nav.properties.add_property') }}</span>
                        </div>
                    </div>
                </div>

                <div class="custom-hr" />
                <div class="p-2 mt-0">
                    <wTT message="main.nav.computed.computed_tooltip" :icon="true"><b>{{ $t("main.nav.computed.title") }}</b></wTT>
                    <div class="mt-2" v-if="globalStore.isLoaded">
                        <template v-for="property in globalStore.properties">
                            <div class="property-item" v-if="property.id < 0">
                                <wTT pos="bottom" :message="'main.nav.computed.' + Math.abs(property.id).toString() + '_tooltip'">
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

</style>