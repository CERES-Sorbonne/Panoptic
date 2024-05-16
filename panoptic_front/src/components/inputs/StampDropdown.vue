<script setup lang="ts">
import { Image, ImagePropertyValue, InstancePropertyValue, PropertyMode, PropertyType } from '@/data/models';
import StampForm from '../forms/StampForm.vue';
import { nextTick, reactive, ref } from 'vue';
import { useProjectStore } from '@/data/projectStore'
import Dropdown from '../dropdowns/Dropdown.vue';
import { isTag, objValues } from '@/utils/utils';
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
    clear()
    dropdownElem.value?.hide()
}

function clear() {
    Object.keys(stamp).forEach((k: any) => delete stamp[k])
    erase.clear()
    nextTick(() => {
        if (dropdownElem.value) {
            dropdownElem.value.focus()
        }
    })
}

async function apply() {

    erase.forEach(k => stamp[k] = undefined)

    const instanceValues: InstancePropertyValue[] = []
    const imageValues: ImagePropertyValue[] = []

    for (let propId of Object.keys(stamp).map(Number)) {
        for (let img of props.images) {
            let stampValue = stamp[propId]
            if (isTag(store.data.properties[propId].type) && img.properties[propId]?.value && stampValue) {
                stampValue = Array.from(new Set([...img.properties[propId].value, ...stampValue]))
            }
            if (store.data.properties[propId].mode == PropertyMode.id) {
                const value: InstancePropertyValue = { propertyId: propId, instanceId: img.id, value: stampValue }
                instanceValues.push(value)
            } else {
                const value: ImagePropertyValue = { propertyId: propId, sha1: img.sha1, value: stampValue }
                imageValues.push(value)
            }
        }
    }
    await store.setPropertyValues(instanceValues, imageValues)

    store.getTabManager().collection.groupManager.clearSelection()
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
                    <StampForm :values="stamp" :erase="erase" @blur="dropdownElem.focus" />
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

    </Dropdown>
</template>