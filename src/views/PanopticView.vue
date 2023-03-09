<script setup>
import { reactive, ref } from 'vue';
import ImageGroup from '../components/ImageGroup.vue';
import ExpandOption from '../components/Menu/ExpandOption.vue';
import MainOption from '../components/Menu/MainOption.vue';
import Property from '../components/Menu/Property.vue';
import TabContent from '../components/TabContent.vue';
import TabNav from '../components/TabNav.vue';
import TagTree from '../components/TagTree/TagTree.vue';
import { fakeStore } from '../fakestore';

const data = reactive({
    selected: [],
    tags: [{name: 'test', children: [{name: 'test1'}, {name: 'test2', children: [{name: 'test34'}]}]}, {name: 'deep', children: [{name: 'egg'}, {name: 'other'}]}]
})

const selectedTab = ref('')

const store = fakeStore

</script>

<template>
    <div class=" ms-5 me-5">
        <div class="row">
            <div class="col-3 bg-warning text-white p-0">
                <div class="bg-secondary" style="height: 55px;">
                    <h1 class="text-center">Panoptic</h1>
                </div>

                <div>
                    <ul class="list-group mt-2">
                        <li class="list-group-item mb-2">
                            <ExpandOption>
                                <template #name>Folder</template>
                                <template #content>
                                    <ul class="list-group">
                                        <li class="list-group-item">/images/vacances</li>
                                        <li class="list-group-item">/theses/collecte</li>
                                        <li class="list-group-item">/racist/lepen</li>
                                    </ul>
                                </template>
                            </ExpandOption>
                        </li>
                        <li class="list-group-item">
                            <MainOption name="Properties">
                                <ul class="list-group">
                                    <li class="list-group-item">Category</li>
                                    <li class="list-group-item"><span class="bi bi-caret-right"></span> Name</li>
                                    <li class="list-group-item">
                                        <Property :name="'Category2'" type="tag-tree" :data="data" />
                                    </li>
                                </ul>
                            </MainOption>
                        </li>
                    </ul>
                </div>
            </div>
            <div class="col">
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