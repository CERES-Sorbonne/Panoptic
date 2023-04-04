<script setup>

import {ref, computed} from 'vue'

const props = defineProps({
    name: String,
    type: String,
})

const expand = ref(true)

const caretClass = computed(() => 'bi bi-caret-right clickable ' + (expand.value ? 'expand' : 'hide'))

function toggle() {
    expand.value = !expand.value
}

</script>

<template>
    <div>
        <h3>{{ props.name }}
            <span class="float-end">
                <i class="bi bi-plus-circle clickable" @click="$emit('addProperty')"></i>
                <span :class="caretClass" @click="toggle"></span>
            </span>
        </h3>

    </div>
    <div v-show="expand" class="ms-2">
        <div class="mt-3"><slot></slot></div>
    </div>
</template>