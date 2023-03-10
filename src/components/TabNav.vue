<script setup>
import { onMounted } from 'vue';
import { fakeStore } from '../fakestore';

const store = fakeStore

// const props = defineProps({ 
//     selected: String
//  })

//  const emits = defineEmits(['update:selected'])


function select(tab) {
    store.selectTab(tab)
}

function newTabName() {
    let counter = store.tabs.length + 1
    let nameFnc = () => 'Tab' + counter
    let name = nameFnc()
    while(store.tabs.includes(name)) {
        counter++
        name = nameFnc()
    }
    return name
}

function addTab(event) {
    let tabName = newTabName()
    store.addTab(tabName)
    store.selectTab(tabName)
}

onMounted(() => {

})

</script>

<template>
    <nav>
        <div class="nav nav-tabs">
            <button v-for="tab in store.tabs" class="nav-link" :class="(tab.name == store.selectedTabName ? ' active' : '')" @click="select(tab.name)"><span class="h4">{{ tab.name }}</span></button>
            <button class="nav-link no-border" @click="addTab"><span class="h3 bi bi-plus"></span></button>
        </div>
    </nav>
</template>

<style>
.no-border{
   border: none !important;
}

</style>