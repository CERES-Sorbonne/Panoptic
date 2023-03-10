<script setup>
import {ref, computed} from 'vue'
import TagTree from '../TagTree/TagTree.vue';

const props = defineProps({
    name: String,
    type: String,
    data: Object
})

const expand = ref(false)

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
        {{ props.name }}
        <span class="float-end">
            <button class="btn btn-sm btn-secondary-outline bi bi-pencil"></button>
            <button class="btn btn-sm btn-secondary-outline bi bi-eye"></button>
        </span>
    </div>
    <div v-show="expand" class="ms-2">
        <template v-if="props.type == 'tag-tree'">
            <TagTree :data="props.data.tags" v-model:selected="props.data.selected"/>
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