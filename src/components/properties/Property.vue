<script setup>
import {ref, computed, reactive} from 'vue'
import { globalStore } from '../../data/store';
import TagTree from '../tagtree/TagTree.vue';
import MultiTagProperty from './TagProperty.vue';

const props = defineProps({
    data: Object,
})

const expand = ref(true)
const filter = reactive({})

const name = computed(() => props.data.name)
const type = computed(() => props.data.type)


const caretClass = computed(() => {
    let className = 'bi bi-caret-right'
    if(expand.value) {
        className += ' expand'
    }
    else {
        className += ' hide'
    }
    return className
})

function toggle() {
    expand.value = !expand.value
}

</script>

<template>
    <div @click="toggle">
        <span :class="caretClass"></span>
        {{ name }}
        <span class="float-end">
            <button class="btn btn-sm btn-secondary-outline bi bi-pencil"></button>
            <button class="btn btn-sm btn-secondary-outline bi bi-eye"></button>
        </span>
    </div>
    <div v-show="expand" class="ms-2">
        <template v-if="['multi_tags', 'tags'].includes(type)">
            <MultiTagProperty :data="props.data" :filter="filter"/>
        </template>
    </div>
</template>

<style>
.bi-caret-right {
    display: inline-block;
    transition: 0.2s;
}


.bi-caret-right.expand{
    transform: rotate(90deg) !important;
}

.bi-caret-right.hide {
    transform: rotate(0deg) !important;
}
</style>