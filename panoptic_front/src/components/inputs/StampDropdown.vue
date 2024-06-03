<script setup lang="ts">
import { ImagePropertyValue, Instance, InstancePropertyValue, PropertyMode, PropertyType } from '@/data/models';
import StampForm from '../forms/StampForm.vue';
import { nextTick, reactive, ref } from 'vue';
import Dropdown from '../dropdowns/Dropdown.vue';
import { isTag } from '@/utils/utils';
import { useDataStore } from '@/data/dataStore';
import { useProjectStore } from '@/data/projectStore';

const data = useDataStore()
const project = useProjectStore()

const props = defineProps<{
    images: Instance[],
    noBorder?: boolean,
    showNumber?: boolean
}>()

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
            if (data.properties[propId].type == PropertyType.multi_tags && img.properties[propId] && stampValue) {
                stampValue = Array.from(new Set([...img.properties[propId], ...stampValue]))
            }
            if (data.properties[propId].mode == PropertyMode.id) {
                const value: InstancePropertyValue = { propertyId: propId, instanceId: img.id, value: stampValue }
                instanceValues.push(value)
            } else {
                const value: ImagePropertyValue = { propertyId: propId, sha1: img.sha1, value: stampValue }
                imageValues.push(value)
            }
        }
    }
    await project.setPropertyValues(instanceValues, imageValues)

    project.getTabManager().collection.groupManager.clearSelection()
    // store.getTabManager().collection.update()
    close()
}

</script>

<template>
    <Dropdown ref="dropdownElem" :teleport="true">
        <template #button>
            <div :class="props.noBorder ? '' : 'button'" style="font-size: 10px; color: rgb(33, 37, 41); padding-bottom: 0.5px;padding-top: 0.5px;">
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