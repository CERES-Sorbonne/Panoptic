<script setup>
import { ref, computed, watch } from 'vue'
import TagNode from './TagNode.vue'
import { globalStore } from '../../data/store';

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



const tagClass = computed(() => {
    let className = 'small-tag'
    if (selected.value) {
        className += ' selected'
    }
    return className
})

const caretClass = computed(() => {
    let className = 'h5 bi bi-caret-right-fill'
    if (expanded.value) {
        className += ' expand'
    }
    else {
        className += ' hide'
    }
    if (anyChildSelected.value) {
        className += ' text-info'
    }

    return className
})

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

function propagateUnselect() {
    props.node.selected = false
    emits("propagate-unselect")
}

function propagateSelect(root) {
    Object.values(root.children).forEach(child => propagateSelect(child))
    root.selected = false
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
    globalStore.addTag(node.property_id, tagName, node.id, null)
    props.node.expanded = true
}

function delTag() {
    let node = props.node
    globalStore.deleteTagParent(node.property_id, node.id, node.localParent).then(() => {
        console.log('deleted')
    })

}

function log(value) {
    console.log(value)
}

</script>

<template>
    <div class="parent-tag-container" :class="anyChildSelected ? ' highlight' : ' normal'" @mouseenter="hover = true"
        @mouseleave="hover = false">
        <a :class="tagClass" @click="selectTag">{{ props.node.value }}</a>
        <span v-if="hasChildren" :class="caretClass" @click="expandTag"></span>
        <span v-if="hover" class="bi bi-plus-square-fill" @click="addTag"></span>
        <span v-if="hover" class="bi bi-dash-square-fill" @click="delTag"></span>
    </div>
    <div class="tag-list" v-show="expanded">
        <TagNode v-for="child in props.node.children" :node="child" @propagate-unselect="propagateUnselect" />
    </div>
</template>

<style>
.tag,
.small-tag {
    display: block;
    width: fit-content;
    border-radius: 100rem;
    margin: 0;
    transition: 0.05s;
    text-decoration: none !important;
    text-align: center;
    color: var(--main-color);
    font-weight: 500;
    border: var(--border-width) solid rgba(var(--main), 0.8);
    background: var(--background-color);
}

.tag:hover,
.small-tag:hover {
    background-color: var(--main-color);
    color: var(--background-color) !important;
    text-decoration: none !important;
}

.tag {
    padding: 0.4rem 0.5rem 0.4rem 0.5rem;
}

.small-tag {
    font-size: 0.85rem;
    padding: 0.3rem 0.4rem 0.3rem 0.4rem;
}

.tag-list {
    flex-direction: column;
}

.tag-list {
    /* display: none; */
    position: relative;
    margin: 0 0 1rem 2rem;
    padding: 0 0 0 1rem;
    height: fit-content;
    z-index: 1;
    border-left: var(--hr);
}

.tag-list .small-tag {
    position: relative;
}

/* Arborescence */

.tag-list .small-tag::before {
    /* balises svg encodées grâce à https://yoksel.github.io/url-encoder/ */
    content: url("data: image/svg+xml, %3Csvg xmlns='http://www.w3.org/2000/svg' width='20' height='4' %3E%3Cpath d='M 0 0 H 20' style='fill:none;stroke:rgb(80, 80, 80);stroke-width:4;' /%3E%3C/svg%3E");
    position: absolute;
    display: block;
    left: -1.2rem;
    top: 0.07;
    z-index: -1;
}

/* Tags parents */
.parent-tag-container {
    display: flex;
    align-items: baseline;
    gap: 0.4rem;
}


.bi-caret-right-fill {
    display: inline-block;
    transition: 0.2s;
}

.bi-caret-right-fill.expand {
    transform: rotate(90deg) !important;
}

.bi-caret-right-fill.hide {
    transform: rotate(0deg) !important;
}
</style>