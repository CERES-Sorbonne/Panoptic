<script setup>
import {ref, computed} from 'vue'
import TagTree from '../TagTree/TagTree.vue';

const props = defineProps({
    data: Object
})

const expand = ref(false)

const name = computed(() => props.data.name)
const type = computed(() => props.data.type)
const values = computed(() => props.data.values)


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
        <template v-if="type == 'multi-tag'">
            <TagTree :data="values" v-model:selected="props.data.selected"/>
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