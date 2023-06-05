<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { globalStore } from '../../data/store';
import TagList from './TagList.vue';
import TagBadge from '../TagTree/TagBadge.vue';

const emits = defineEmits(['propagate-unselect'])

const props = defineProps({
    node: { type: Object, required: true }
})

const hover = ref(false)
const selected = computed(() => props.node.selected)
const expanded = computed(() => props.node.expanded)
const hasChildren = computed(() => Object.keys(props.node.children).length)
const anyChildSelected = computed(() => {
    return allChildren(props.node).some(c => c.selected && c.localId !== props.node.localId)
})

const backgroundStyle = computed(() => { return 'background-color: #' + props.node.color + '!important;' })


function selectTag() {
    props.node.selected = !props.node.selected
    if (props.node.selected) {
        emits('propagate-unselect')
        Object.values(props.node.children).forEach(propagateSelect)
    }
}

function expandTag() {
    console.log(expanded.value)
    props.node.expanded = !props.node.expanded
}


function allChildren(root) {
    let res = [root]
    if (!Object.values(root.children).length) {
        return res
    }
    Object.values(root.children).map(allChildren).forEach(arr => res.push(...arr))
    return res
}

function addTag() {
    let node = props.node
    let tagName = prompt('Tag Name')
    if (!tagName) {
        return
    }
    globalStore.addTag(node.property_id, tagName, node.id, node.color)
    props.node.expanded = true
}

function delTag() {
    globalStore.deleteTagParent(props.node.id, props.node.localParent).then(() => {
        console.log('deleted')
    })

}

// onMounted(() => console.log(props.node))

</script>

<template>
    <div class="node" @mouseenter="hover = true" @mouseleave="hover = false">
        <TagBadge :tag="props.node.value" :color="props.node.color" />
        <!-- <span v-if="hasChildren" class="bi bi-chevron-right" @click="expandTag"></span> -->
        <span v-if="hover" class="bi bi-plus-square-fill ms-1 btn-icon" @click="addTag"></span>
        <span v-if="hover" class="bi bi-dash-square-fill ms-1 btn-icon" @click="delTag"></span>
    </div>
    <div v-if="hasChildren">
        <TagList :tags="props.node.children" />
    </div>
</template>

<style scoped>
.tag-text {
    margin-left: 3px;
    padding: 4px;
    padding-left: 6px;
    padding-right: 6px;
    border-radius: 5px;
}
</style>
