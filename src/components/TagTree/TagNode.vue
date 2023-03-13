<script setup>
import {ref, computed, watch} from 'vue'
import TagNode from './TagNode.vue'


const props = defineProps({
    data: {type: Object, required: true}
})

// const selected = ref(false)
const selected = computed(() => props.data.selected)

const tagClass = computed(() => {
    let className = 'small-tag'
    if(selected.value) {
        className += ' selected'
    }
    return className
})

function selectTag() {
    props.data.selected = ! props.data.selected
}

watch(selected, (value) => {
    if(!value && props.data.children) {
        for(let child of props.data.children) {
            child.selected = false
        }
    }
})

</script>

<template>
    <a v-if="!props.data.children" :class="tagClass" @click="selectTag">{{ props.data.name }}</a>
    <template v-else>
        <div class="parent-tag-container">
            <a :class="tagClass" @click="selectTag">{{ props.data.name }}</a>
            <div class="parent-arrow" :style="'transform: ' + (selected ? 'rotate(90deg);' : 'none;')"></div>
        </div>
        <div class="tag-list" v-show="selected">
            <TagNode v-for="child in props.data.children" :data="child"/>
        </div>
    </template>
    

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

.parent-arrow::before {
    content: url("data:image/svg+xml,%3Csvg width='11' height='12' viewBox='0 0 11 12' fill='none' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M9.75 4.70096C10.75 5.27831 10.75 6.72169 9.75 7.29904L2.25 11.6292C1.25 12.2065 -5.89441e-07 11.4848 -5.38967e-07 10.3301L-1.60415e-07 1.66987C-1.09942e-07 0.51517 1.25 -0.206516 2.25 0.370835L9.75 4.70096Z' fill='rgb(80, 80, 80)'/%3E%3C/svg%3E%0A");
}

.parent-arrow {
    /* transform: none; */
    transition: 0.1s;
}

.parent-arrow:hover {
    cursor: pointer;
}

</style>