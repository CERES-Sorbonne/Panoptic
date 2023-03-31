<script setup lang="ts">

import { V_MODEL_SELECT } from '@vue/compiler-dom';
import { onMounted, reactive } from 'vue';
import { globalStore } from '../../data/store';
import ExpandOption from './ExpandOption.vue';
import * as models from '../../data/models'
import PropertyForm from '../forms/PropertyForm.vue';
import TagProperty from '../properties/TagProperty.vue';
import Property from '../properties/Property.vue';

</script>

<template>
    <div class="bg-secondary" style="height: 55px;">
        <h1 class="text-center">Panoptic</h1>
    </div>

    <div>
        <ul class="list-group mt-2">
            <li class="list-group-item">
                <ExpandOption title-size="h3">
                    <template #name> Folders </template>
                    <template #icons><span @click.stop="globalStore.importFolders"
                            class=" h4 bi bi-folder-plus me-3"></span></template>
                    <template #content>
                        <ul class="list-group" @click.stop>
                            <li class="list-group-item" v-for="folder in globalStore.params.folders">{{ folder }}</li>
                        </ul>
                    </template>
                </ExpandOption>
            </li>
            <li class="list-group-item">
                <ExpandOption title-size="h3">
                    <template #name>Properties </template>
                    <template #icons><span @click.stop="" class="h4 bi bi-plus-square me-3 btn-icon" data-bs-toggle="modal"
                            data-bs-target="#propForm"></span></template>
                    <template #content>
                        <ul class="list-group">
                            <li class="list-group-item" v-for="property in globalStore.properties">
                                <TagProperty v-if="property.type == models.PropertyType.multi_tags || property.type == models.PropertyType.tag" :data="property"/>
                                <Property v-else :data="property"/>
                            </li>
                        </ul>
                    </template>
                </ExpandOption>
            </li>
        </ul>
    </div>

    <PropertyForm id="propForm"/>

</template>