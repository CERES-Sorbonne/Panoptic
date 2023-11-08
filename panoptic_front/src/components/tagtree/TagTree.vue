<script setup>

import { globalStore } from '../../data/store';
import TagList from '../foldertree/TagList.vue';

const emits = defineEmits(['update:selected'])

const props = defineProps({
    root: { type: Object, required: true },
    selected: { type: Array, required: true },
    propertyId: { type: Number, required: true }
})


// function tagName(parentPath, tagName) {
//     if (parentPath == '') {
//         return tagName
//     }
//     return parentPath + '.' + tagName
// }

// function recursiveSelected(node, parentPath = '') {
//     let res = []
//     if (node.selected) {
//         return [tagName(parentPath, node.value)]
//     }
//     if (!node.selected && !node.children) {
//         return res
//     }
//     if (node.children) {
//         node.children.map(c => recursiveSelected(c, tagName(parentPath, node.value)))
//             .forEach(arr => res.push(...arr))
//     }
//     return res
// }

// watch(() => props.root, (root) => {
//     let res = []
//     for (let node in root.children) {
//         res.push(...recursiveSelected(node))
//     }
//     emits('update:selected', res)
// },
//     { deep: true }
// )

function addRootTag() {
    let value = prompt('tag name: ')
    if (!value) {
        return
    }
    globalStore.addTag(props.propertyId, value, undefined)
}

</script>

<template>
    <span class="bi bi-plus-square-fill ms-2" @click="addRootTag"></span>
    <div class="ms-0">
        <TagList :tags="props.root.children" />
    </div>
</template>


<style>

</style>