<script setup>
import { reactive, watch, onMounted, computed } from 'vue';
import { globalStore } from '../../store';
import TagTree from '../TagTree/TagTree.vue';

const props = defineProps({
    data: Object
})

const tagStates = reactive({})
const tagTree = reactive({})

const tags = computed(() => globalStore.tags[props.data.id])

function create_state(tagId) {
    let state = Object.assign({}, tags.value[tagId])
    state.selected = false
    state.expanded = false
    return state
}

function updateTreeState() {
    Object.keys(tags.value).forEach(tId => {

        if(!tagStates[tId]) {
            tagStates[tId] = create_state(tId)
        }
    })

    Object.keys(tagStates).forEach(tId => {
        if(!tags.value[tId]) {
            delete tagStates[tId]
        }
    })
}

function recursiveBuildTree(node, parentId) {
    let nodeId = parentId + '.' + node.id
    let tree = node
    if(tree.children) {
        let children = {}
        Object.vlaues(tree.children).forEach()
    }
}

function buildTree(root) {
    let res = Object.values(root).map(node => recursiveBuildTree(node, 0))
    let tree = {}
    res.forEach(r => tree[r.id] = r)
    return tree
}

watch(() => props.data, (data) => {
    updateTreeState()
})

onMounted(() => {
    updateTreeState()
})

</script>

<template>
    {{ globalStore.tagTrees }}
    <!-- <TagTree :data="values" v-model:selected="props.data.selected"/> -->
</template>