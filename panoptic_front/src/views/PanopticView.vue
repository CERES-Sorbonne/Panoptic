<script setup lang="ts">

import { ref } from 'vue';
import TabContent from '../components/images/TabContent.vue';
import TabNav from '../components/images/TabNav.vue';
import Menu from '../components/Menu/Menu.vue';
import { Modals } from '@/data/models';
import ImageModal from '@/components/modals/ImageModal.vue';
import PropertyModal from '@/components/modals/PropertyModal.vue';
import { globalStore } from '@/data/store';

</script>

<template>
    <div class="d-flex flex-row">
        <div class="">
            <Menu />
        </div>
        <div style="width: 100%;" class="me-3" v-if="globalStore.isLoaded">
            <div class="ms-3">
                <TabNav />
            </div>
            <div class="custom-hr" />
            <TabContent :tab="globalStore.tabs[globalStore.selectedTab]" />
        </div>

    </div>

    <ImageModal :id="Modals.IMAGE" />
    <PropertyModal :id="Modals.PROPERTY" />
</template>