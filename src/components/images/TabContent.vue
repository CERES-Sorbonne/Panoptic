<script setup>
import { reactive, computed, watch, onMounted, ref } from 'vue';
import { fakeStore } from '../../fakestore';
import ImageGroup from './ImageGroup.vue';
import DropdownInput from '../inputs/DropdownInput.vue';
import ListInput from '../inputs/ListInput.vue';
import { globalStore } from '../../data/store';

const store = fakeStore
const imageSize = ref(100)

const options = store.options
const tab = computed(() => store.tabs.find(t => t.name == store.selectedTabName))
const state = computed(() => tab.value.state)
const groups = computed(() => tab.value.groups)

const groups2 = reactive([])

function computeGroups() {
    // TODO filter

    groups2.length = 0
    
    let allGroup = {
        name: 'all',
        images: Object.values(globalStore.images)
    }
    groups2.push(allGroup)
}

onMounted(computeGroups)


watch(tab, () => {
    store.saveTabState()
}, {deep: true})

watch(() => globalStore.images, computeGroups)

</script>

<template>
    <div class="d-flex flex-wrap mb-3 mt-3">
        <div class="bd-highlight mt-1 me-1">
            <div class="input-group">
                <div class="input-group-text">Display</div>
                <DropdownInput :options="options.display" v-model="state.display"/>
            </div>
        </div>
        <div class="bd-highlight mt-1 me-1">
            <ListInput label="Filters" :selected="state.filter" :possible="options.filter"/>
        </div>
        <div class="bd-highlight mt-1 me-1">
            <ListInput label="GroupBy" :selected="state.groupBy" :possible="options.groupBy"/>
        </div>
    </div>
    <div class="mt-4">
        <i class="h2 bi bi-aspect-ratio me-3"></i>
        <input type="range" class="form-range" id="rangeImageSize" min="50" max="200" v-model="imageSize" style="width: 300px;">

        <ImageGroup :leftAlign="true" v-for="group in groups2" :group="group" :imageSize="imageSize"/>
    </div>

</template>