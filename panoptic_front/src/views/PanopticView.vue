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
    <div class="d-flex flex-row">
        <div class="">
            <Menu />
        </div>
        <div style="width: 100%;" class="me-3">
            <div class="ms-3">
                <TabNav v-model:selected="selectedTab" />
            </div>
            <div class="custom-hr" />
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