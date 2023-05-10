<script setup lang="ts">

import { ref } from 'vue';
import TabContent from '../components/images/TabContent.vue';
import TabNav from '../components/images/TabNav.vue';
import Menu from '../components/menu/Menu.vue';
import { Modals } from '@/data/models';
import ImageModal from '@/components/modals/ImageModal.vue';
import PropertyModal from '@/components/modals/PropertyModal.vue';
import { globalStore } from '@/data/store';


const selectedTab = ref('')

</script>

<template>
    <div class="row">
        <div class="col-2 bg-warning text-white p-0">
            <Menu />
        </div>
        <div class="col-9">
            <br />
            <!-- <textarea :value="JSON.stringify(globalStore.tagTrees['1'], null, 4)" rows="20" cols="80"></textarea> -->
            <div style="min-height: 55px;">
                <TabNav v-model:selected="selectedTab" />
            </div>
            <template v-for="tab, index in globalStore.tabs">
                <div v-if="globalStore.selectedTabName == tab.name">
                    <TabContent :tab-index="index" />
                </div>
            </template>
        </div>

    </div>

    <ImageModal :id="Modals.IMAGE" />
    <PropertyModal :id="Modals.PROPERTY" />
</template>