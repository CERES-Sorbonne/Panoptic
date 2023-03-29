<script setup>

import { reactive, ref, computed } from 'vue';
import TabContent from '../components/layout/TabContent.vue';
import TabNav from '../components/layout/TabNav.vue';
import { fakeStore } from '../fakestore';
import { globalStore } from '../data/store';
import Menu from '../components/menu/Menu.vue';


const selectedTab = ref('')

const files = reactive({})
const store = fakeStore

const tags = computed(() => globalStore.tagTrees)

</script>

<template>
    <div class=" ms-5 me-5">
        <div class="row">
            <div class="col-4 bg-warning text-white p-0">
                <Menu />
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