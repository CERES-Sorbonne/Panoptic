<script setup lang="ts">
import { Image } from '@/data/models';
import StampForm from '../forms/StampForm.vue';
import { onMounted, reactive, ref } from 'vue';
import * as bootstrap from 'bootstrap'
import { globalStore } from '@/data/store';


const props = defineProps({
    images: Array<Image>
})

const stamp = reactive({}) as any
const buttonElem = ref(null)

function close() {
    let dropdown = bootstrap.Dropdown.getOrCreateInstance(buttonElem.value)
    dropdown.hide()
    clear()
}

function clear() {
    Object.keys(stamp).forEach((k: any) => delete stamp[k])
}

function apply() {
    props.images.forEach(img => {
        Object.keys(stamp).forEach((propId) => {
            let value = stamp[propId]
            globalStore.addOrUpdatePropertyToImage(img.sha1, propId, value)
        })
    })
    close()
}

</script>

<template>
    <!-- <div class="btn-group"> -->
        <button data-bs-toggle="dropdown" aria-expanded="false" data-bs-auto-close="outside"
            ref="buttonElem">
            Tampon
        </button>
        <div class="dropdown-menu">
            <div class="m-2" style="width: 300px;">
                <StampForm :values="stamp" />
            </div>

            <div class="d-flex float-end pe-2">
                <button class="me-2" @click="close">Cancel</button>
                <button class="me-2" @click="clear">Clear</button>
                <button class="me" @click="apply">Apply</button>
            </div>
        </div>
    <!-- </div> -->
</template>