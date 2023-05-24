<script setup lang="ts">

import { globalStore } from '../../data/store';
import ExpandOption from './ExpandOption.vue';
import * as models from '../../data/models'
import TagProperty from '../properties/TagProperty.vue';
import Property from '../properties/Property.vue';
import { Modals } from '../../data/models';
import { reactive, ref } from 'vue';
import FolderList from '../FolderTree/FolderList.vue';


let isFolderLoading = ref(false)

const addFolder = async () => {
    isFolderLoading.value = true
    await globalStore.importFolders()
    isFolderLoading.value = false
}

</script>

<template>
    <div class="menu overflow-scroll">
        <div class="">
            <div>
                <div class="p-2">
                    <b>Dossiers</b>
                    <FolderList v-if="globalStore.tabs[globalStore.selectedTab]" :folders="globalStore.folderTree" :tab="globalStore.tabs[globalStore.selectedTab].data"/>
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
                <div class="custom-hr" />
                <div class="p-2 mt-0">
                    <b>Properties</b>
                    <div class="mt-2" v-if="globalStore.isLoaded">
                        <template v-for="property in globalStore.properties">
                            <div class="property-item" v-if="property.id >= 0">
                                <TagProperty
                                    v-if="property.type == models.PropertyType.multi_tags || property.type == models.PropertyType.tag"
                                    :data="property" />
                                <Property v-else :data="property" />
                            </div>
                        </template>

                        <div @click="globalStore.showModal(Modals.PROPERTY)" class="btn-icon property-item"
                            style="line-height: 25px;">
                            <i class="bi bi-plus btn-icon float-start" style="font-size: 25px;"></i>
                            <span>Nouvelle propriété</span>
                        </div>
                    </div>
                </div>

                <div class="custom-hr" />
                <div class="p-2 mt-0">
                    <b>Computed</b>
                    <div class="mt-2" v-if="globalStore.isLoaded">
                        <template v-for="property in globalStore.properties">
                            <div class="property-item" v-if="property.id < 0">
                                <TagProperty
                                    v-if="property.type == models.PropertyType.multi_tags || property.type == models.PropertyType.tag"
                                    :data="property" />
                                <Property v-else :data="property" />
                            </div>
                        </template>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<style>.option-content {
    width: 100%
}</style>