<script setup>
import { reactive, computed, watch } from 'vue';
import { fakeStore } from '../../fakestore';
import ImageGroup from './ImageGroup.vue';
import DropdownInput from '../inputs/DropdownInput.vue';
import ListInput from '../inputs/ListInput.vue';

const store = fakeStore

// const props = defineProps({
//     tabName: String
// })


// const state = reactive({
//     display: 'grid',
//     filter: ['filter1', 'filter2', 'filter3'],
//     groupBy: ['value1', 'value2'],
// })

// const options = reactive({
//     display: ['grid', 'list','3eme Oeil'],
//     filter: ['filter1', 'filter2', 'filter3', 'other1', 'other2', 'toto', 'felix', 'darmanin'],
//     groupBy: ['filter1', 'filter2', 'toto', 'darmanin']
// })

const options = store.options
const tab = computed(() => store.tabs.find(t => t.name == store.selectedTabName))
const state = computed(() => tab.value.state)
const groups = computed(() => tab.value.groups)

// const groups = reactive([
//     {
//         name: "Group1",
//         groups: [
//             {name: 'SubGroup11', images: 15},
//             {name: 'SubGroup12', images: 12}
//         ]
//     },
//     {
//         name: "Group2",
//         groups: [
//             {name: 'SubGroup21', images: 4},
//             {name: 'SubGroup22', images: 7}
//         ]
//     },
// ])

watch(tab, () => {
    store.saveTabState()
}, {deep: true})

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
    {{ state }}
    <div class="mt-4">
        <ImageGroup :leftAlign="true" v-for="group in groups" :group="group"/>
    </div>

</template>