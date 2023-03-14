<script setup lang="ts">

import { reactive, computed, onMounted, watch } from 'vue';
import { globalStore } from '../../store';
import { PropsTree, TagsTree, TreeTag } from '../../utils/models';
import TagTree from '../TagTree/TagTree.vue';

interface NodeState extends TreeTag{
    expanded: boolean
    selected: boolean
}

const props = defineProps({
    data: Object,
    filter: Object
})

type StateDict =  {[key: string]: NodeState}


const nodeStates: StateDict = reactive({})
const localTree = <NodeState>reactive({})


const id = computed(() => props.data.id)
const rootNode = computed(() => (globalStore.tagTrees as any)[id.value][0] as TreeTag)



// function create_state(tagId) {

// }

// function updateTreeState() {
//     Object.keys(tags.value).forEach(tId => {

//         if(!tagStates[tId]) {
//             tagStates[tId] = create_state(tId)
//         }
//     })

//     Object.keys(tagStates).forEach(tId => {
//         if(!tags.value[tId]) {
//             delete tagStates[tId]
//         }
//     })
// }

// function getNodeState(tagNode: TreeTag) {
//     if(nodeStates[tagNode.localId]) {
//         Object.assign(nodeStates[tagNode.localId], {name: tagNode.name})
//         return nodeStates[tagNode.localId]
//     }
//     let state = Object.assign({}, tagNode)
//     state.children =
// }

function createOrUpdateState(tagNode: TreeTag) {
    if(!nodeStates[tagNode.localId]) {
        nodeStates[tagNode.localId] = Object.assign({}, {...tagNode, expanded: false, selected: false})
    }
    else {
        Object.assign(nodeStates[tagNode.localId], tagNode)
    }
    nodeStates[tagNode.localId].children = {}
    return nodeStates[tagNode.localId]
}

function copyTree(root: TreeTag) {
    let state = createOrUpdateState(root)
    
    if(root.children) {
        Object.values(root.children).forEach((child: TreeTag)  => {
            state.children[child.id] = copyTree(child)
        })
    }

    return state
}

onMounted(() => {
    let res = copyTree(rootNode.value)
    localTree.children = res.children
})

watch(rootNode, () => {
    let res = copyTree(rootNode.value)
    localTree.children = res.children
})

const selected = reactive([])

</script>

<template>
    <TagTree :root="localTree" v-model:selected="selected"/>
</template>