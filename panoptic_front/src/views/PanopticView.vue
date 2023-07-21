<script setup lang="ts">

import { ref, computed, onMounted, nextTick, onUnmounted } from 'vue';
import TabContent from '../components/images/TabContent.vue';
import TabNav from '../components/images/TabNav.vue';
import Menu from '../components/menu/Menu.vue';
import { Modals } from '@/data/models';
import ImageModal from '@/components/modals/ImageModal.vue';
import PropertyModal from '@/components/modals/PropertyModal.vue';
import { globalStore } from '@/data/store';
import Sha1PileModal from '@/components/modals/Sha1PileModal.vue';


const navElem = ref(null)

const windowHeight = ref(400)

const contentHeight = computed(() => windowHeight.value - (navElem.value?.clientHeight ?? 0))

onMounted(() => {
    nextTick(() => {
        window.addEventListener('resize', onResize);
        onResize()
    })
})

onUnmounted(() => {
    window.removeEventListener('resize', onResize);
})

function onResize() {
    windowHeight.value = window.innerHeight
}


</script>

<template>
    <div class="d-flex flex-row m-0 p-0 overflow-hidden">
        <div class="">
            <Menu />
        </div>

        <div class="w-100" v-if="globalStore.isLoaded">

            <div class="ms-3" ref="navElem">
                <TabNav />
            </div>
            <div class="custom-hr" />
            <TabContent :tab="globalStore.tabs[globalStore.selectedTab]" :height="contentHeight"
                v-if="globalStore.isLoaded && globalStore.tagTrees" />
        </div>
        <div v-else class="loading">
            <i class="spinner-border" role="status"></i>
            <span class="ms-1">Loading...</span>
        </div>
    </div>

    <ImageModal :id="Modals.IMAGE" />
    <PropertyModal :id="Modals.PROPERTY" />
    <Sha1PileModal :id="Modals.SHA1PILE" />

    <!-- <div class="above bg-info">lalala</div>
                <div class="above2 bg-warning">lalala</div> -->
</template>

<style scoped>
.above {
    position: absolute;
    top: 500px;
    left: 500px;
    z-index: 200;
}

.above2 {
    position: absolute;
    top: 500px;
    left: 500px;
}

.loading {
    width: 100%;
    height: 100vh;
    display: flex;
    justify-content: center;
    align-items: center;
}
</style>