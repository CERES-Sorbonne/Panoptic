<script setup lang="ts">

import { ModalId, Property } from '@/data/models';
import { ref, reactive } from 'vue';
import PropertyTypeDropdown from '@/components/dropdowns/PropertyTypeDropdown.vue';
import { useProjectStore } from '@/data/projectStore';
import { useDataStore } from '@/data/dataStore';
import PropertyModeDropdown from '../dropdowns/PropertyModeDropdown.vue';
import Modal2 from './Modal2.vue';

const project = useProjectStore()
const data = useDataStore()

const newProperty = reactive({}) as Property

const message = ref('')


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

    const prop = await data.addProperty(newProperty.name, newProperty.type, newProperty.mode)
    project.getTabManager().setVisibleProperty(prop.id, true)
    hide()
}

</script>


<template>
    <Modal2 :id="ModalId.PROPERTY" :max-height="170" :max-width="600">
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