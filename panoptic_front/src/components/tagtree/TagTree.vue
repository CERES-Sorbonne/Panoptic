<script setup>
import { watch } from 'vue';
import TagNode from './TagNode.vue';
import { globalStore } from '../../data/store';

const emits = defineEmits(['update:selected'])

const props = defineProps({
    root: {type: Object, required: true},
    selected: {type: Array, required: true},
    propertyId: {type: Number, required: true}
})


function tagName(parentPath, tagName) {
    if(parentPath == '') {
        return tagName
    }
    return parentPath + '.' + tagName
}

function recursiveSelected(node, parentPath='') {
    let res = []
    if(node.selected) {
        return [tagName(parentPath, node.value)]
    }
    if(!node.selected && !node.children) {
        return res
    }
    if(node.children) {
        node.children.map(c => recursiveSelected(c, tagName(parentPath, node.value)))
        .forEach(arr => res.push(...arr))
    }
    return res
}

watch(() => props.root, (root) => {
    let res = []
    for(let node in root.children) {
        res.push(...recursiveSelected(node))
    }
    emits('update:selected', res)
}, 
{deep: true}
)

function addRootTag() {
    let value = prompt('tag name: ')
    if(!value) {
        return
    }
    globalStore.addTag(props.propertyId, value, undefined)
}

</script>

<template>
    <span class="bi bi-plus-square-fill" @click="addRootTag"></span>
    <div id="tags-panel-container">
        <nav id="tags-panel">
            <!-- <div id="title-button-container">
                <p><strong>Recherche de contenus par concepts</strong></p>
                <a class="arrow" onclick="show_panel(this)">→</a>
            </div>
            <div id="tags-panel-text">
                <p>Cliquez sur les concepts pour les inclure dans la recherche, cliquez sur les flèches pour afficher
                    les
                    sous-concepts</p>
                <input type="text" placeholder="Recherche dans le texte">
                <a class="button">Lancer la recherche →</a>
            </div>
            <hr> -->
            <!-- {{ props.root }} -->
            <div id="tags-panel-tree">
                <TagNode :node="node" v-for="node in props.root.children"/>
            </div>
        </nav>
    </div>
</template>


<style>
/* Blocs flexbox du panneau */

#tags-panel-text {
    /* visibility: hidden; */
    font-size: 95%;
    flex: 0 1 auto;
}

#title-button-container {
    font-size: 1rem;
    display: flex;
    gap: 1rem;
    align-items: center;
}

#title-button-container>p {
    /* visibility: hidden; */
}

#tags-panel>hr {
    /* visibility: hidden; */
    width: 100%;
    margin: 1rem 0 0 0;
}

#tags-panel-tree {
    /* visibility: hidden; */
    flex: 1 1 auto;
    padding: 0;
    margin: 0;
    overflow-y: scroll;
    overflow-x: scroll;
    /* Cacher la barre de défilement pour Internet Explorer, Edge et Firefox */
    -ms-overflow-style: none;
    scrollbar-width: none;
}

/* Cacher la barre de défilement pour Chrome, Safari et Opera */
#tags-panel-tree::-webkit-scrollbar {
    display: none;
}

/* Tags du panneau */

#tags-panel-tree .small-tag {
    /* color: var(--disabled-color); */
    /* border-color: var(--disabled-color); */
    margin-top: 0.5rem;
    cursor: pointer;
}

#tags-panel-tree .small-tag:hover {
    border-color: rgba(var(--main), 0.6) !important;
    background-color: var(--background-color);
    color: rgba(var(--main), 0.9) !important;
}

#tags-panel-tree .small-tag.selected {
    /* color: green !important; */
    /* color: var(--main-color) !important; */
    background-color: turquoise;
    color: black;
    border-color: var(--main-color) !important;
}

/* Listes de tags */

#tags-panel-tree,
.tag-list {
    flex-direction: column;
}

</style>