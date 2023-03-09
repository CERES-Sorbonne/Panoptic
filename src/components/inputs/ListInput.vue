<script setup>
import { computed, ref } from 'vue';



const props = defineProps({
    label: String,
    selected: Array,
    possible: Array
})

const optionFilter = ref('')

const available = computed(() => {
    return props.possible
    .filter(v => !props.selected.includes(v))
    .filter(v => v.includes(optionFilter.value))

})


function remove(value) {
    let index = props.selected.indexOf(value)
    if(index < 0) {
        return
    }
    props.selected.splice(index, 1)
}

function add(value) {
    optionFilter.value = ''
    props.selected.push(value)
}

</script>

<template>
    <div class="input-group">
        <div class="input-group-text">{{ label }}</div>
        <div v-for="value in selected" class="input-group-text bg-white">{{ value }} <i @click="remove(value)" class="bi bi-x-circle ms-1 text-danger"></i></div>
        <button type="button" class="btn btn-sm btn-outline-secondary dropdown-toggle caret-off p-0" data-bs-toggle="dropdown" aria-expanded="false">
            <i class="h4 bi bi-plus"></i>
        </button>
        <ul class="dropdown-menu">
            <li class="ms-1 me-1"><input type="text" class="form-control form-control-sm" v-model="optionFilter" placeholder="Search.."/></li>
            <li><hr class="dropdown-divider"></li>
            <li v-for="option in available"><a class="dropdown-item" href="#" @click="add(option)">{{ option }}</a></li>
        </ul>
    </div>
</template>

<style>

.caret-off::before {
    display: none !important;
}
.caret-off::after {
    display: none !important;
}
</style>