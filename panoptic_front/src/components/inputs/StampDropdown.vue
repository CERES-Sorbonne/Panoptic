<script setup lang="ts">
import { Image, PropertyType } from '@/data/models';
import StampForm from '../forms/StampForm.vue';
import { nextTick, reactive, ref } from 'vue';
import { useProjectStore } from '@/data/projectStore'
import Dropdown from '../dropdowns/Dropdown.vue';
const store = useProjectStore()

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

async function apply() {

    erase.forEach(k => stamp[k] = undefined)

    Object.keys(stamp).map(Number).forEach(async propId => {
        let value = stamp[propId]
        if(store.data.properties[propId].type == PropertyType.multi_tags) {
            const mode = value != undefined ? 'add' : 'set'
            await store.setTagPropertyValue(propId, props.images, value, mode)
        }
        else {
            await store.setPropertyValue(propId, props.images, value, true)
        }
    })
    store.getTabManager().collection.update()
    close()
}

</script>

<template>
    <Dropdown ref="dropdownElem" :teleport="true">
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
                        {{ $t('modals.tagging.cancel') }}
                    </button>
                    <button class="me-2" @click="clear">
                        {{ $t('modals.tagging.clear') }}
                    </button>
                    <button class="me" @click="apply">
                        {{ $t('modals.tagging.apply') }}
                    </button>
                </div>
            </div>
        </template>

</Dropdown></template>