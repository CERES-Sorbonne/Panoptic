<script setup>
import { reactive } from 'vue';
import TagTree from '../components/TagTree/TagTree.vue';

const data = reactive([{name: 'test', children: [{name: 'test1'}, {name: 'test2', children: [{name: 'test34'}]}]}, {name: 'deep', children: [{name: 'egg'}, {name: 'other'}]}])
const selectedTags = reactive([])
const state = reactive({selected: []})
</script>

<template>
    <TagTree :data="data" v-model:selected="state.selected"/>
    {{ state.selected }}
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
                <div class="row mt-2">
                    <div>
                        <h4 class="text-center">Folders</h4>
                    </div>
                    <div>
                        <ul class="list-group">
                            <li class="list-group-item">/images/vacances</li>
                            <li class="list-group-item">/theses/collecte</li>
                            <li class="list-group-item">/racist/lepen</li>
                        </ul>
                    </div>
                </div>

                <div class="row mt-2">
                    <div>
                        <h4 class="text-center">Properties</h4>
                    </div>
                    <div>
                        <ul class="list-group">
                            <li class="list-group-item">Category</li>
                            <li class="list-group-item">Name</li>
                            <li class="list-group-item">Category 2
                            </li>
                        </ul>
                    </div>
                </div>
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
                <div class="mt-3">
                    <div class="mb-3">
                        <h3 class="mb-3"><i class="bi bi-caret-down"></i> Group1 (27 images) <i class="h5 bi bi-share"></i></h3>
                        <div class="ms-5">
                            <div>
                                <h4><i class="bi bi-caret-down"></i> Subgroup 1 (15 images) <i class="h6 bi bi-share"></i></h4>
                                <div class="row ms-4">
                                    <div class="col-1 bg-success m-2" v-for="i in 15" style="width: 100px; height: 100px;"></div>
                                </div>
                            </div>
                            <div>
                                <h4><i class="bi bi-caret-down"></i> Subgroup 2 (12 images) <i class="h6 bi bi-share"></i></h4>
                                <div class="row ms-4">
                                    <div class="col-1 bg-success m-2" v-for="i in 12" style="width: 100px; height: 100px;"></div>
                                </div>
                            </div>
                        </div>
                        
                    </div>
                    <div>
                        <h3><i class="bi bi-caret-right-fill"></i> Group2 (10 images) <i class="h5 bi bi-share"></i></h3>
                    </div>
                </div>
            </div>
        </div>
    </div>

</template>