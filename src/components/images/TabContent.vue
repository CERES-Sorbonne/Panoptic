<script setup lang="ts">
import { reactive, computed, watch, onMounted, ref } from 'vue';
import ImageGroup from './ImageGroup.vue';
import DropdownInput from '../inputs/DropdownInput.vue';
import ListInput from '../inputs/ListInput.vue';
import { globalStore } from '../../data/store';
import * as boostrap from 'bootstrap'
import FilterInputDropdown from '../inputs/FilterInputDropdown.vue';
import { createCompoundExpression } from '@vue/compiler-core';
import { Images } from '@/data/models';
import { computeGroupFilter } from '@/utils/filter';

const props = defineProps({
    tabIndex: Number
})

const imageSize = ref('100')

const tab = computed(() => globalStore.params.tabs[props.tabIndex])

const groups2 = reactive([])

const filteredImages = computed(() => {
    let images = Object.values(globalStore.images)
    return images.filter(img => computeGroupFilter(img, tab.value.filter))
})

function computeGroups() {
    groups2.length = 0

    let allGroup = {
        name: 'all',
        images: filteredImages.value
    }
    groups2.length = 0
    groups2.push(allGroup)
}
onMounted(computeGroups)


watch(tab, () => {
    globalStore.saveTabState()
}, { deep: true })

watch(filteredImages, computeGroups, {deep: true})

</script>

<template>
    <!-- <div class="d-flex flex-wrap mb-3 mt-3">
        <div class="bd-highlight mt-1 me-1">
            <div class="input-group">
                <div class="input-group-text">Display</div>
                <DropdownInput :options="options.display" v-model="state.display" />
            </div>
        </div>
        <div class="bd-highlight mt-1 me-1">
            <ListInput label="Filters" :selected="state.filter" :possible="options.filter" />
        </div>
        <div class="bd-highlight mt-1 me-1">
            <ListInput label="GroupBy" :selected="state.groupBy" :possible="options.groupBy" />
        </div>
    </div> -->
    <FilterInputDropdown v-model="globalStore.params.tabs[props.tabIndex].filter"/>
    <div class="mt-4">
        <i class="h2 bi bi-aspect-ratio me-3"></i>
        <input type="range" class="form-range" id="rangeImageSize" min="50" max="200" v-model="imageSize"
            style="width: 300px;">
        <span class="ms-2">({{ imageSize }}px)</span>
        <div class="float-end me-5">
            <div class="input-group">
                <div class="input-group-text">PageSize</div>
                <input class="form-control" type="number" v-model="globalStore.settings.pageSize" style="width: 100px;" />
            </div>
        </div>

        <ImageGroup :leftAlign="true" v-for="group in groups2" :group="group" :imageSize="imageSize" />
    </div>
</template>