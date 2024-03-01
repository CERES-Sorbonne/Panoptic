<script setup lang="ts">
import { nextTick, reactive, ref } from 'vue';
import 'splitpanes/dist/splitpanes.css'

//default styles
import 'vue3-draggable-resizable/dist/Vue3DraggableResizable.css'
import TextInput from '@/components/inputs/TextInput.vue';


var emptyImage = new Image();
emptyImage.src = 'data:image/gif;base64,R0lGODlhAQABAIAAAAUEBAAAACwAAAAAAQABAAACAkQBADs=';

const text = ref("Lorem Ipsum is simply dummy text of the printing and typesetting industry. Lorem Ipsum has been the industry's standard dummy text ever since the 1500s, when an unknown printer took a galley of type and scrambled it to make a type specimen book. It has survived not only five centuries, but also the leap into electronic typesetting, remaining essentially unchanged. It was popularised in the 1960s with the release of Letraset sheets containing Lorem Ipsum passages, and more recently with desktop publishing software like Aldus PageMaker including versions of Lorem Ipsum.")
const edit = ref(false)
const contentElem = ref(null)
const inputElem = ref(null)

const areaH = ref(0)
const areaW = ref(0)

const state = reactive({
    x: 100,
    y: 100,
    h: 100,
    w: 100,
    active: false
})


const cols = reactive([1, 2, 3, 4, 5].map(x => ({ id: x, size: 50 })))

function updateText() {
    text.value = contentElem.value.innerText
}

function setEdit() {
    areaH.value = contentElem.value.clientHeight
    areaW.value = contentElem.value.clientWidth
    console.log(areaH.value)
    edit.value = true
    nextTick(() => inputElem.value.focus())
}

function logEvent(event: any, id) {
    console.log(event)
    console.log(id)
}

function print(v) {
    console.log(v)

}

function allowDrop(ev) {
//   ev.preventDefault();
//   console.log('lala')
}

function drag(ev) {
//   ev.dataTransfer.setData("text", ev.target.id);
}

function drop(ev) {
//   ev.preventDefault();
//   var data = ev.dataTransfer.getData("text");
//   ev.target.appendChild(document.getElementById(data));
}

function resize(ev, id) {
    console.log(ev.offsetX)
    // ev.dataTransfer.setDragImage(undefined, 0, 0)
    cols[id-2].size += ev.offsetX
}

function dragStart(event) {
    event.dataTransfer.setDragImage(emptyImage, 0, 0);
}

</script>

<template>
    <!-- <splitpanes style="height: 400px" @resize="logEvent">
        <pane v-for="col in cols" :size="col.size">{{ col.id }}</pane>
    </splitpanes> -->

    <!-- <div class="parent">
        <Vue3DraggableResizable :initW="200" :init-h="30" v-model:x="state.x" v-model:y="state.y" v-model:w="state.w"
            v-model:h="state.h" v-model:active="state.active" :draggable="true" :resizable="true" :disabledH="true" :disabledY="true" :disabled-x="true"
            @activated="print('activated')" @deactivated="print('deactivated')" @drag-start="print('drag-start')"
            @resize-start="print('resize-start')" @dragging="print('dragging')" @resizing="print('resizing')"
            @drag-end="print('drag-end')" @resize-end="print('resize-end')">
            This is a test example
        </Vue3DraggableResizable>

    </div> -->


    <!-- <DraggableContainer :disabled="false">
        <Vue3DraggableResizable>
            Test
        </Vue3DraggableResizable>
        <Vue3DraggableResizable>
            Another test
        </Vue3DraggableResizable>
    </DraggableContainer> -->
<!-- 
    <div class="d-flex flex-row">
        <template v-for="col, index in cols">
            <div class="limit" @drop="drop" @dragstart="dragStart" @dragover="allowDrop" @drag="e => resize(e, col.id)" draggable="true"></div>
            <div  class="p-2" :style="{width: col.size + 'px'}" draggable="true" @drop="print">
            {{ col.id }}
        </div>
        </template>
       
    </div> -->

    <div class="d-flex flex-row">
        <template v-for="col, index in cols">
            <!-- <div class="limit" @drop="drop" @dragstart="dragStart" @dragover="allowDrop" @drag="e => resize(e, col.id)" draggable="true"></div> -->
            <div  class="p-2 resize-col" :style="{width: col.size + 'px'}" @resize="print" draggable="true">
            {{ col.id }}
        </div>
        </template>
       
    </div>
    <TextInput tag="p" :contenteditable="true" v-model="text" :no-nl="false" :no-html="true" @update:height="print"/>
    <div><p>{{ text }}</p></div>
    <div class="m-5" style="width: 200px;">
        <!-- <p ref="contentElem" :contenteditable="true" @input="e => text = e.target.innerText">{{ text }}</p> -->
        
        <!-- <textarea rows="1" ref="inputElem" @focusout="edit = false" v-show="edit" v-model="text"
            :style="'height: ' + areaH + 'px; width: ' + areaW + 'px; resize: none;'"></textarea>
        <p v-show="!edit" @click="setEdit" ref="contentElem">{{ text }}</p> -->
    </div>
</template>

<style>

.resize-col {
    overflow: hidden;
    resize: horizontal;
    border: none;
}

.limit {
    border-left: 2px solid var(--border-color);
    cursor: pointer;
    padding-right: 2px;
}

p {
    max-width: 100%;
    width: 100%;
    white-space: pre-wrap;
    word-break: break-word;
    caret-color: rgb(55, 53, 47);
    padding: 3px 3px;
}

textarea:focus {
    outline: none;
    padding: 2px 2px !important;
    margin: 0px;
    border: 1px solid blue;
}

.splitpanes__pane {
    display: flex;
    /* justify-content: center; */
    /* align-items: center; */
    font-family: Helvetica, Arial, sans-serif;
    color: rgba(255, 255, 255, 0.6);
    background-color: green;
    /* font-size: 5em; */
}

.parent {
    width: 200px;
    height: 200px;
    position: relative;
    border: 1px solid #000;
    user-select: none;
    text-align: left;
}
</style>