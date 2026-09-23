<script setup lang="ts">

import { ModalId, Property } from '@/data/models';
import { ref, reactive } from 'vue';
import PropertyTypeDropdown from '@/components/dropdowns/PropertyTypeDropdown.vue';
import { useProjectStore } from '@/data/stores/projectStore';
import { useDataStore } from '@/data/stores/dataStore';
import PropertyModeDropdown from '../dropdowns/PropertyModeDropdown.vue';
import Modal2 from './Modal2.vue';
import { useTabStore } from '@/data/stores/tabStore';
import { useModalStore } from '@/data/stores/modalStore';

const project = useProjectStore()
const data = useDataStore()
const tabStore = useTabStore()

const newProperty = reactive({}) as Property

const message = ref('')

const group = ref(undefined)
// Called with the new property once it exists, for a caller that opened the modal to use it
// right away (the group view's "Assign to… → New property").
let onCreated: ((prop: Property) => void) | undefined

async function saveProperty(hide) {
    console.log('halloo')
    if (!newProperty.name) {
        message.value = 'modals.properties.no_name'
        return
    }
    let propNames = data.propertyList.map(p => p.name)
    if (propNames.includes(newProperty.name)) {
        message.value = 'modals.properties.not_unique_name'
        return
    }

    if (!newProperty.type) {
        message.value = "modals.properties.no_type"
    }

    const prop = await data.addProperty(newProperty.name, newProperty.type, newProperty.mode, group.value ?? null)
    tabStore.getMainTab().setVisibleProperty(prop.id, true)
    onCreated?.(prop)

    // if (group.value != undefined && group.value >= 0) {
    //     console.log(prop)
    //     await data.updateProperty(prop.id, prop.name, group.value)
    // }
    hide()
}

function onShow(data) {
    Object.keys(newProperty).forEach(k => delete newProperty[k])
    if(data?.mode) {
        newProperty.mode = data.mode
    }
    if(data?.type) {
        newProperty.type = data.type
    }
    onCreated = data?.onCreated
    if(data?.group) {
        group.value = data.group
    } else {
        group.value = undefined
    }
}

</script>


<template>
    <Modal2 :id="ModalId.PROPERTY" :layer="1" :max-height="170" :max-width="600" @show="onShow">
        <template #title>
            {{ $t("modals.properties.title") }}
        </template>
        <template #content="{ hide }">
            <div class="d-flex p-2 justify-content-center">
                <div class="me-1">
                    <PropertyModeDropdown v-model="newProperty.mode" />
                </div>
                <div>
                    <input type="text" style="width: 100%" class="" id="propertyName" name="propertyName"
                        v-model="newProperty.name" :placeholder="$t('modals.properties.input')">
                </div>
                <div class="ms-1">
                    <PropertyTypeDropdown id="select-property" v-model="newProperty.type" class="input-lg" />
                </div>
            </div>

            <div class="text-center">
                <span v-if="message" class="text-warning">{{ $t(message) }}</span>
                <span v-else>{{ $t('modals.properties.message') }}</span>
            </div>

            <div class="d-flex p-2 justify-content-center">
                <!-- <div class="flex-grow-1"></div> -->
                <div class="bbb me-2" @click="hide">{{ $t("modals.properties.cancel") }}</div>
                <div class="bbb" @click="saveProperty(hide)">{{
                    $t("modals.properties.confirm") }}</div>
            </div>
        </template>
    </Modal2>
</template>

<style scoped>
input {
    border: 1px solid var(--border-color);
    border-radius: 3px;
}
</style>