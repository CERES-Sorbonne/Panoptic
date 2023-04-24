<script setup lang="ts">
import { Image, Property, PropertyValue } from '@/data/models';
import { computed, nextTick, ref } from 'vue';
import { PropertyType } from '@/data/models';
import { globalStore } from '@/data/store';
import { PropertyRef } from '@/data/models'
import PropertyIcon from '../properties/PropertyIcon.vue';

const props = defineProps({
    property: Object as () => PropertyRef,
    maxSize: String
})

const edit = ref(false)
const inputElem = ref(null)


const isSet = computed(() => props.property.value || props.property.value == 0)
const type = computed(() => props.property.type)

function setEdit(value: Boolean) {
    if (value) {
        edit.value = true
        document.addEventListener('click', handleContainerClick, true)
        nextTick(() => {
            if (!inputElem.value) {
                return
            }
            inputElem.value.focus()
        })
    }
    else {
        document.removeEventListener('click', handleContainerClick)
        globalStore.addOrUpdatePropertyToImage(props.property.imageSHA1, props.property.propertyId, props.property.value)
        edit.value = false
        if (props.property.value == '') {
            props.property.value = undefined
        }
    }
}

const handleContainerClick = (event: any) => {
    if (!edit.value) {
        return
    }
    if (inputElem.value && !inputElem.value.contains(event.target)) {
        setEdit(false)

        if (!elemIsInput(event.target, 10)) {
            event.stopPropagation()
        }
    }
};

function elemIsInput(elem: HTMLElement, depth: number = 0): Boolean {
    if (elem.getAttribute('is-input')) {
        return true
    }
    if (depth > 0 && elem.parentElement) {
        return elemIsInput(elem.parentElement, depth - 1)
    }
    return false
}


function inputType(type: PropertyType) {
    switch (type) {
        case PropertyType.number:
            return 'number'
        case PropertyType.date:
            return 'date'
        case PropertyType.color:
            return 'color'
        case PropertyType.checkbox:
            return 'checkbox'
        default:
            return 'text'
    }
}

</script>


<template>
    <form @submit.prevent="setEdit(false)" is-input="true" class="pt-1 pb-1 bg-light pe-1 overflow-hidden">
        <div class="d-flex flex-row" @click="setEdit(true)">
            <div class="bg-light text-dark me-1">
                <span class="me-1">
                    <input v-if="type == PropertyType.checkbox" class="small-input" type="checkbox"
                        v-model="props.property.value" @change="setEdit(false)">
                    <span @click="setEdit(true)" v-else>
                        <PropertyIcon :type="property.type" />
                    </span>
                </span>
                <span v-if="!edit && !(type == PropertyType.checkbox)" @click="setEdit(true)">
                    <span v-if="!isSet" class="text-secondary">None</span>
                    <span v-else-if="type != PropertyType.color">{{ props.property.value }}</span>
                </span>
            </div>
            <template v-if="type == PropertyType.color && isSet">
                <input type="color" class="" v-model="props.property.value" />
            </template>
            <div v-if="edit && type != PropertyType.checkbox" class="w-100">
                <input :type="inputType(type)" class="small-input   " ref="inputElem" v-model="props.property.value" />
            </div>
            <div v-if="type == PropertyType.checkbox">
                {{ globalStore.properties[props.property.propertyId].name }}
            </div>
        </div>
    </form>
</template>


<style>
.small {
    margin: 0px !important;
    padding: 0px !important;
    border: 0 !important;
    border-radius: 0 !important;
}

.small-input {
    padding: 0;
    padding-left: 0.3em;
    margin: 0;
    border: none;
    width: 100%;
}
</style>