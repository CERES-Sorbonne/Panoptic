<script setup>

import { ref } from 'vue';
import TabContent from '../components/images/TabContent.vue';
import TabNav from '../components/images/TabNav.vue';
import { fakeStore } from '../fakestore';
import Menu from '../components/menu/Menu.vue';
import ImageForm from '@/components/forms/ImageForm.vue';
import { globalStore } from '@/data/store';
import { Modals } from '@/data/models';


const selectedTab = ref('')
const store = fakeStore

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
            <div v-if="store.selectedTabName">
                <TabContent />
            </div>

        </div>

    </div>

    <ImageForm :id="Modals.IMAGE" />
</template>