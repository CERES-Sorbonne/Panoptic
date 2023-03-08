<script setup>
import { reactive } from 'vue';
import ImageGroup from '../components/ImageGroup.vue';
import ExpandOption from '../components/Menu/ExpandOption.vue';
import MainOption from '../components/Menu/MainOption.vue';
import Property from '../components/Menu/Property.vue';
import TagTree from '../components/TagTree/TagTree.vue';

const data = reactive({
    selected: [],
    tags: [{name: 'test', children: [{name: 'test1'}, {name: 'test2', children: [{name: 'test34'}]}]}, {name: 'deep', children: [{name: 'egg'}, {name: 'other'}]}]
})


const groups = reactive([
    {
        name: "Group1",
        groups: [
            {name: 'SubGroup11', images: 15},
            {name: 'SubGroup12', images: 12}
        ]
    },
    {
        name: "Group2",
        groups: [
            {name: 'SubGroup21', images: 4},
            {name: 'SubGroup22', images: 7}
        ]
    },
])

</script>

<template>
    <div class=" ms-5 me-5">
        <div class="row">
            <div class="col-3 bg-secondary text-white" style="height: 55px;">
                <!-- <div class="row"> -->
                    <h1 class="text-center">Panoptic</h1>
                <!-- </div> -->
            </div>
            <div class="col bg-info">
                <div class="d-flex align-items-center" style="height: 55px;">
                    <ul class="nav d-flex align-items-center">
                        <li class="nav-item">
                            <a class="nav-link" aria-current="page" href="#">Tab1</a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="#">Tab2</a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="#">Tab3</a>
                        </li>
                    </ul>
                </div>
            </div>
        </div>
        <div class="row">
            <div class="col-3 bg-warning">
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
            <div class="col">
                <div class="input-group mt-1">
                    <div class="input-group-text">Display</div>
                    <button class="btn btn-outline-secondary dropdown-toggle" type="button" data-bs-toggle="dropdown" aria-expanded="false">Grid</button>
                    <ul class="dropdown-menu dropdown-menu-end">
                        <li><a class="dropdown-item" href="#">Graph</a></li>
                        <li><a class="dropdown-item" href="#">LA VERITÉ SUR MARCRON</a></li>
                    </ul>
                    <div class="input-group-text ms-1">Filters</div>
                    <div class="input-group-text bg-white">Filter 1 <i class="bi bi-x-circle ms-2 text-danger"></i></div>
                    <div class="input-group-text bg-white">Filter 2 <i class="bi bi-x-circle ms-2 text-danger"></i></div>
                    <div class="input-group-text bg-white">Filter 3 <i class="bi bi-x-circle ms-2 text-danger"></i></div>
                    <button class="btn btn-outline-secondary">+</button>

                    <div class="input-group-text ms-1">Group By</div>
                    <div class="input-group-text bg-white">Name <i class="bi bi-x-circle ms-2 text-danger"></i></div>
                    <div class="input-group-text bg-white">Tags <i class="bi bi-x-circle ms-2 text-danger"></i></div>
                    <button class="btn btn-outline-secondary">+</button>
                </div>
                <div class="mt-4">
                    <ImageGroup :leftAlign="true" v-for="group in groups" :group="group"/>
                </div>
            </div>
        </div>
    </div>

</template>