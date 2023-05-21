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
                    <FolderList :folders="globalStore.folderTree" />
                </div>
                <div class="custom-hr" />
                <div class="p-2 mt-0">
                    <b>Properties</b>
                    <div class="mt-2" v-if="globalStore.isLoaded">
                        <div v-for="property in globalStore.properties" class="property-item">
                            <TagProperty
                                v-if="property.type == models.PropertyType.multi_tags || property.type == models.PropertyType.tag"
                                :data="property" />
                            <Property v-else :data="property" />
                        </div>
                        <div @click="globalStore.showModal(Modals.PROPERTY)" class="btn-icon property-item" style="line-height: 25px;">
                            <i class="bi bi-plus btn-icon float-start" style="font-size: 25px;"></i>
                            <span>Nouvelle propriété</span>
                        </div>
                    </div>
                </div>
                <!-- <ExpandOption title-size="h6">
                    <template #name> </template>
                    <template #icons><span @click="globalStore.showModal(Modals.PROPERTY)"
                            class="h4 bi bi-plus-square me-3 btn-icon"></span></template>
                    <template #content>
                        <ul class="list-group option-content">
                            <li class="list-group-item" v-for="property in globalStore.properties">
                                <TagProperty
                                    v-if="property.type == models.PropertyType.multi_tags || property.type == models.PropertyType.tag"
                                    :data="property" />
                                <Property v-else :data="property" />
                            </li>
                        </ul>
                    </template> -->
                <!-- </ExpandOption> -->
            </div>
        </div>
    </div>
</template>

<style>
.option-content {
    width: 100%
}

</style>