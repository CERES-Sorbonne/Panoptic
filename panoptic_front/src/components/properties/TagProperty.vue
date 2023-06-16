<script setup lang="ts">

import { reactive, computed, onMounted, watch } from 'vue';
import { globalStore } from '@/data/store';
import { Property, TreeTag } from '../../data/models';
import TagTree from '../tagtree/TagTree.vue';

interface NodeState extends TreeTag{
    expanded: boolean
    selected: boolean
}

const props = defineProps({
    data: Object as () => Property,
    filter: Object
})

type StateDict =  {[key: string]: NodeState}

const nodeStates: StateDict = reactive({})
const localTree = reactive({}) as NodeState


const id = computed(() => props.data.id)
const rootNode = computed(() => globalStore.tagTrees[id.value])


function createOrUpdateState(tagNode: TreeTag) {
    if(!nodeStates[tagNode.localId]) {
        nodeStates[tagNode.localId] = Object.assign({}, {...tagNode, expanded: false, selected: false})
    }
    else {
        Object.assign(nodeStates[tagNode.localId], tagNode)
    }
    nodeStates[tagNode.localId].children = []
    return nodeStates[tagNode.localId]
}

function copyTree(root: TreeTag) {
    let state = createOrUpdateState(root)
    
    if(root.children) {
        root.children.forEach((child: TreeTag)  => {
            state.children.push(copyTree(child))
        })
    }
    return state
}

function updateTree() {
    let res = copyTree(rootNode.value)
    Object.assign(localTree, {...res, propertyId: id.value})
    // localTree.children = res.children
}

onMounted(() => {
    updateTree()
})

watch(rootNode, () => {
    updateTree()
})

const selected = reactive([])
</script>

<template>
    <TagTree :root="localTree" v-model:selected="selected" :property-id="id"/>
</template>