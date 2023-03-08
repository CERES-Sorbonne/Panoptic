<script setup>

import {ref, computed} from 'vue'

const props = defineProps({
    name: String,
    type: String,
})

const expand = ref(true)

const caretClass = computed(() => {
    let className = 'bi bi-caret-right'
    if(expand.value) {
        className += ' expand'
    }
    else {
        className += ' hide'
    }
    return className
})

function toggle() {
    expand.value = !expand.value
}

</script>

<template>
    <div @click="toggle">
        <h3>{{ props.name }}
            <span class="float-end">
                <span :class="caretClass"></span>
            </span>
        </h3>

    </div>
    <div v-show="expand" class="ms-2">
        <div class="mt-3"><slot></slot></div>
    </div>
</template>

<style>
.bi-caret-right {
    display: inline-block;
    transition: 0.2s;
}


.bi-caret-right.expand{
    transform: rotate(90deg) !important;
}

.bi-caret-right.hide {
    transform: rotate(0deg) !important;
}
</style>