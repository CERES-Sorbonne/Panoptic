<script setup>
import { watch } from 'vue';
import TagNode from './TagNode.vue';

const emits = defineEmits(['update:selected'])

const props = defineProps({
    data: {type: Array, required: true},
    selected: {type: Array, required: true}
})

function tagName(parentPath, tagName) {
    if(parentPath == '') {
        return tagName
    }
    return parentPath + '.' + tagName
}

function recursiveSelected(node, parentPath='') {
    let res = []
    if(!node.selected) {
        return res
    }
    if(node.children) {
        let selectedChildren = node.children.filter(c => c.selected)
        if(selectedChildren.length == node.children.length || selectedChildren.length == 0) {
            return [tagName(parentPath, node.name)]
        }
        else {
            for(let child of node.children) {
                res.push(...recursiveSelected(child, tagName(parentPath, node.name)))
            }
            return res
        }
    }
    return [tagName(parentPath, node.name)]
}

watch(() => props.data, (data) => {
    console.log('lala')
    let res = []
    for(let node of data) {
        res.push(...recursiveSelected(node))
    }
    console.log(res)
    emits('update:selected', res)
}, 
{deep: true}
)

</script>

<template>
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
            <div id="tags-panel-tree">
                <TagNode :data="data" v-for="data in props.data"/>
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
    overflow-x: hidden;
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