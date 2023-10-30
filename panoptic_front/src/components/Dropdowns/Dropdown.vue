<script setup lang="ts">
import { onMounted, ref } from 'vue';
import * as bootstrap from 'bootstrap'

const emits = defineEmits(['show', 'hide'])
defineExpose({ hide, show })

const buttonElem = ref(null)
let dropdown: bootstrap.Dropdown

const visible = ref(false)

function hide() {
    dropdown.hide()

}

function show() {
    dropdown.show()

}

function onShow() {
    visible.value = true
    emits('show')
    
}

function onHide() {
    visible.value = false
    emits('hide')
}

onMounted(() => {
    buttonElem.value.addEventListener('show.bs.dropdown', () => onShow())
    buttonElem.value.addEventListener('hide.bs.dropdown', () => onHide())
    dropdown = bootstrap.Dropdown.getOrCreateInstance(buttonElem.value)
})

</script>

<template>
    <div class="dropdown p-0 m-0" style="position: static;">
        <div class="m-0 p-0" data-bs-toggle="dropdown" aria-expanded="false" data-bs-auto-close="outside" ref="buttonElem">
            <slot name="button"></slot>
        </div>
        <div class="dropdown-menu bg-white m-0 p-0">
            <slot name="popup" v-if="visible"></slot>
        </div>
    </div>
</template>

<style scoped>
.dropdown-menu {
    font-size: 14px;
    border: 1px solid var(--border-color);
    /* box-shadow: 2px 2px 4px 0px rgba(195,202,217,1);
-webkit-box-shadow: 2px 2px 4px 0px rgba(195,202,217,1);
-moz-box-shadow: 2px 2px 4px 0px rgba(195,202,217,1); */
box-shadow: 0px 0px 15px 1px var(--border-color);
-webkit-box-shadow: 0px 0px 6px 3px var(--border-color);
-moz-box-shadow: 0px 0px 15px 1px var(--border-color);
}
</style>