<script setup lang="ts">
import { Image, PropertyType } from '@/data/models';
import StampForm from '../forms/StampForm.vue';
import { onMounted, reactive, ref } from 'vue';
import * as bootstrap from 'bootstrap'
import { globalStore } from '@/data/store';


const props = defineProps({
    images: Array<Image>,
    noBorder: Boolean,
    showNumber: Boolean
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
    Object.keys(stamp).map(Number).forEach( propId => {
        let value = stamp[propId]
        let mode = globalStore.properties[propId].type == PropertyType.multi_tags ? 'add' : null
        globalStore.setPropertyValue(propId, props.images, value, mode)
    });
    close()
}

</script>

<template>
    <!-- <div class="btn-group"> -->
    <div :class="props.noBorder? '' : 'button'" data-bs-toggle="dropdown" aria-expanded="false" data-bs-auto-close="outside" ref="buttonElem">
        <span v-if="props.showNumber">{{ $t('main.menu.tag_selection') + ' ' + props.images.length  + ' ' + $t('main.menu.selected_images')}}</span>
        <span v-else>{{$t('modals.tagging.button')}}</span>
    </div>
    <div class="dropdown-menu">
        <div class="m-2" style="width: 300px;">
            <StampForm :values="stamp" />
        </div>

        <div class="d-flex float-end pe-2">
            <button class="me-2" @click="close">{{$t('modals.tagging.cancel')}}</button>
            <button class="me-2" @click="clear">{{$t('modals.tagging.clear')}}</button>
            <button class="me" @click="apply">{{$t('modals.tagging.apply')}}</button>
        </div>
    </div>
    <!-- </div> -->
</template>