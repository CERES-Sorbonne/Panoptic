<script setup lang="ts">
import { Image, PropertyType } from '@/data/models';
import StampForm from '../forms/StampForm.vue';
import { nextTick, onMounted, onUnmounted, reactive, ref } from 'vue';
import * as bootstrap from 'bootstrap'
import { globalStore } from '@/data/store';
import Dropdown from '../dropdowns/Dropdown.vue';
import wTT from '../tooltips/withToolTip.vue';


const props = defineProps({
    images: Array<Image>,
    noBorder: Boolean,
    showNumber: Boolean
})

const stamp = reactive({}) as any
const erase = reactive(new Set()) as Set<number>
const dropdownElem = ref(null)
const popupElem = ref(null)

function close() {
    dropdownElem.value?.hide()
    clear()
}

function clear() {
    Object.keys(stamp).forEach((k: any) => delete stamp[k])
    erase.clear()
    nextTick(() => dropdownElem.value.focus())
}

function apply() {
    Object.keys(stamp).map(Number).forEach(propId => {
        let value = stamp[propId]
        let mode = globalStore.properties[propId].type == PropertyType.multi_tags ? 'add' : null
        globalStore.setPropertyValue(propId, props.images, value, mode)
    });
    close()
}


function onClick(e) {
    if (popupElem.value && popupElem.value.contains(e.target)) {
        console.log('inside')
    }
    else {
        e.stopPropagation()
        close()
    }
}

// function onShow() {
//     document.addEventListener('click', onClick, true)
// }

// function onHide() {
//     document.removeEventListener('click', onClick, true)
// }

// onMounted(() => {
//     buttonElem.value.addEventListener('hide.bs.dropdown', onHide)
//     buttonElem.value.addEventListener('show.bs.dropdown', onShow)

// })
</script>

<template>
    <Dropdown ref="dropdownElem">
        <template #button>
            <div :class="props.noBorder ? '' : 'button'">
                <span v-if="props.showNumber">{{ $t('main.menu.tag_selection') + ' ' + props.images.length + ' ' +
                    $t('main.menu.selected_images') }}</span>
                <span v-else>{{ $t('modals.tagging.button') }}</span>
            </div>
        </template>
        <template #popup>
            <div @keydown.escape.prevent.stop="">
                <div class="m-2" style="width: 300px;">
                    <StampForm :values="stamp" :erase="erase" @blur="dropdownElem.focus"/>
                </div>

                <div class="d-flex pe-2 mb-2">
                    <div class="flex-grow-1"></div>
                    <button class="me-2" @click="close">
                        <wTT :message="$t('tmp')">{{ $t('modals.tagging.cancel') }}</wTT>
                    </button>
                    <button class="me-2" @click="clear">
                        <wTT :message="$t('tmp')">{{ $t('modals.tagging.clear') }}</wTT>
                    </button>
                    <button class="me" @click="apply">
                        <wTT :message="$t('tmp')">{{ $t('modals.tagging.apply') }}</wTT>
                    </button>
                </div>
            </div>
        </template>

</Dropdown></template>