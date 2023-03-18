<script setup>

import { reactive, ref, computed } from 'vue';
import ExpandOption from '../components/Menu/ExpandOption.vue';
import MainOption from '../components/Menu/MainOption.vue';
import Property from '../components/properties/Property.vue';
import TabContent from '../components/layout/TabContent.vue';
import TabNav from '../components/layout/TabNav.vue';
import { fakeStore } from '../fakestore';
import { globalStore } from '../data/store';

const data = reactive({
    selected: [],
    tags: [{name: 'test', children: [{name: 'test1'}, {name: 'test2', children: [{name: 'test34'}]}]}, {name: 'deep', children: [{name: 'egg'}, {name: 'other'}]}]
})

const selectedTab = ref('')

const files = reactive({})
const store = fakeStore

const tags = computed(() => globalStore.tagTrees)

</script>

<template>
    <div class=" ms-5 me-5">
        <div class="row">
            <div class="col-4 bg-warning text-white p-0">
                <div class="bg-secondary" style="height: 55px;">
                    <h1 class="text-center">Panoptic</h1>

                </div>

                <div>
                    <ul class="list-group mt-2">
                        <li class="list-group-item mb-2">
                            <ExpandOption>
                                <template #name> Folders </template>
                                <template #icons><span @click.stop="globalStore.importFolders" class=" h4 bi bi-folder-plus me-3"></span></template>
                                <template #content>
                                    <ul class="list-group" @click.stop>
                                        <li class="list-group-item" v-for="folder in globalStore.params.folders">{{ folder }}</li>
                                    </ul>
                                </template>
                            </ExpandOption>
                        </li>
                        <li class="list-group-item">
                            <MainOption name="Properties">
                                <ul class="list-group">
                                    <li class="list-group-item" v-for="property in globalStore.properties">
                                        <Property :data="property" />
                                    </li>
                                </ul>
                            </MainOption>
                        </li>
                    </ul>
                </div>
            </div>
            <div class="col">
                <br />
                <!-- <textarea :value="JSON.stringify(globalStore.tagTrees['1'], null, 4)" rows="20" cols="80"></textarea> -->
                <div style="min-height: 55px;">
                    <TabNav v-model:selected="selectedTab"/>
                </div>
                <div v-if="store.selectedTabName">
                    <TabContent/>
                </div>
                
            </div>
        </div>
    </div>

</template>