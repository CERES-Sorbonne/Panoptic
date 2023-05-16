<script setup lang="ts">

import { reactive, computed, onMounted, watch } from 'vue';
import { globalStore } from '@/data/store';
import { TreeTag } from '../../data/models';
import ExpandOption from '../Menu/ExpandOption.vue';
import { PropertyType } from '../../data/models';
import TagTree from '../TagTree/TagTree.vue';
import PropertyIcon from './PropertyIcon.vue';

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
const rootNode = computed(() => globalStore.tagTrees[id.value])
const type = computed(() => props.data.type)


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
    <ExpandOption title-size="b" :left-align="false" :default-expand="false">
        <template #name>
            <PropertyIcon :type="type" />
            {{ props.data.name }}
        </template>
        <template #icons>
            <!-- <span @click.stop="" class="bi bi-pencil btn-icon me-3"></span> -->
            <span @click.stop="props.data.show = !props.data.show" :class="'bi bi-eye btn-icon text-' + (props.data.show ? 'primary' : 'secondary')"></span>
        </template>
        <template #content>
            <TagTree :root="localTree" v-model:selected="selected" :property-id="id"/>
        </template>
    </ExpandOption>
    
</template>