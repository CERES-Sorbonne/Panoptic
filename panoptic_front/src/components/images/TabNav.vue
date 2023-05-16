<script setup lang="ts">

import { globalStore } from '@/data/store';
import { onMounted } from 'vue';

// const props = defineProps({ 
//     selected: String
//  })

//  const emits = defineEmits(['update:selected'])


function select(tab: string) {
    globalStore.selectTab(tab)
}

function newTabName() {
    let counter = globalStore.tabs.length + 1
    let nameFnc = () => 'Tab' + counter
    let name = nameFnc()
    while(globalStore.tabs.map(t => t.name).includes(name)) {
        counter++
        name = nameFnc()
    }
    return name
}

function addTab(event: any) {
    let tabName = newTabName()
    globalStore.addTab(tabName)
    globalStore.selectTab(tabName)
}

onMounted(() => {

})

</script>

<template>
    <nav>
        <div class="d-flex d-row">
            <button v-for="tab in globalStore.tabs" class="tab-button" :class="(tab.name == globalStore.selectedTabName ? ' active' : '')" @click="select(tab.name)"><span>{{ tab.name }}</span></button>
            <button class="tab-icon ms-2" @click="addTab"><span class="bi bi-plus"></span></button>
        </div>
    </nav>
</template>

<style>
.no-border{
   border: none !important;
}

</style>